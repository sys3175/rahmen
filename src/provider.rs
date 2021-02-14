//! Utilities to provide images, and other abstractions

use std::convert::{TryFrom, TryInto};
use std::io::BufReader;
use std::path::Path;

use convert_case::{Case, Casing};
use image::{DynamicImage, Pixel};
use itertools::Itertools;
use pyo3::prelude::*;
use regex::Regex;
use rexiv2::Metadata;

use crate::config::{Element, Replacement};
use crate::errors::{RahmenError, RahmenResult};

/// Provider trait to produce images, or other types
pub trait Provider<D> {
    /// Obtain the next element.
    /// Error -> Terminate
    /// Ok(Some(T)) -> Process T
    /// Ok(None) -> Exhausted
    fn next_image(&mut self) -> RahmenResult<Option<D>>;
}

impl<D> Provider<D> for Box<dyn Provider<D>> {
    fn next_image(&mut self) -> RahmenResult<Option<D>> {
        (**self).next_image()
    }
}

fn load_jpeg<P: AsRef<Path>>(path: P, max_size: Option<usize>) -> RahmenResult<DynamicImage> {
    let mut d = mozjpeg::Decompress::with_markers(mozjpeg::ALL_MARKERS).from_path(&path)?;

    if let Some(max_size) = max_size {
        let mut scale = 8;
        let ratio_to_max_size = max_size as f32 / (d.width() * d.height()) as f32;
        if ratio_to_max_size < 1. {
            scale = (ratio_to_max_size * 8.) as u8 + 1;
        }
        d.scale(scale);
    }
    let mut decompress_started = d.to_colorspace(mozjpeg::ColorSpace::JCS_EXT_BGR)?;
    let height = decompress_started.height();
    let mut img = DynamicImage::new_bgr8(decompress_started.width() as _, height as _);
    let buffer: Option<Vec<[u8; 3]>> = decompress_started.read_scanlines();
    let rgb_img = img.as_mut_bgr8().unwrap();
    if let Some(buffer) = buffer {
        for (row, row_buffer) in buffer.chunks(buffer.len() / height).enumerate() {
            for (col, pixel) in row_buffer.iter().enumerate() {
                *rgb_img.get_pixel_mut(col as _, row as _) = *image::Bgr::from_slice(pixel);
            }
        }
        Ok(img)
    } else {
        eprintln!("Failed to decode image: {:?}", path.as_ref());
        Err(RahmenError::Retry)
    }
}

/// Load an image from a path
pub fn load_image_from_path<P: AsRef<Path>>(
    path: P,
    max_size: Option<usize>,
) -> RahmenResult<DynamicImage> {
    let _t = crate::Timer::new(|e| println!("Loading {}ms", e.as_millis()));
    println!("Loading {:?}", path.as_ref());
    match image::ImageFormat::from_path(&path)? {
        image::ImageFormat::Jpeg => load_jpeg(path, max_size),
        format => {
            image::io::Reader::with_format(BufReader::new(std::fs::File::open(&path)?), format)
                .decode()
                .map_err(Into::into)
        }
    }
}

/// settings for the status line formatter
#[derive(Debug, Deserialize, Clone)]
pub struct LineSettings {
    /// the separator to insert between the metadata
    pub separator: String,
    /// should we deduplicate metadata?
    pub uniquify: bool,
    /// should we hide empty metadata?
    pub hide_empty: bool,
}

/// The following are the ops concerning the status line (text being displayed below the image)

/// Tries to convert a string slice to a Case
pub fn str_to_case(s: String) -> RahmenResult<Case> {
    let case_str = s.to_case(Case::Flat);
    for case in Case::all_cases() {
        if case_str == format!("{:?}", case).to_case(Case::Flat) {
            return Ok(case);
        }
    }
    Err(RahmenError::CaseUnknown(s))
}

/// abstract runtime definitions for the transformation ops for the meta data entries
#[derive(Debug)]
enum StatusLineTransformation {
    RegexReplace(Regex, String),
    Capitalize,
    ChangeCase(Case, Case),
}

/// runtime transformation ops for the metadata values (the parameters are gathered in the try_from function)
impl StatusLineTransformation {
    fn transform<S: AsRef<str>>(&self, input: S) -> String {
        match self {
            Self::RegexReplace(re, replacement) => re
                .replace_all(input.as_ref(), replacement.as_str())
                .into_owned(),
            Self::Capitalize => input.as_ref().from_case(Case::Upper).to_case(Case::Title),
            Self::ChangeCase(f, t) => input.as_ref().from_case(*f).to_case(*t),
        }
    }
}

/// prepare ops (regexes/replacements) to process the complete status line
impl TryFrom<Replacement> for StatusLineTransformation {
    type Error = RahmenError;
    /// build each status line element with its transformations and the tag
    fn try_from(value: Replacement) -> Result<Self, Self::Error> {
        // collect the transformation ops and store their parameters
        // iterate over the regex(es)

        Ok(StatusLineTransformation::RegexReplace(
            Regex::new(value.regex.as_ref())?,
            value.replace,
        ))
    }
}

/// a status line meta data element: a string and transformations to perform on it
#[derive(Debug)]
struct StatusLineElement {
    tags: Vec<String>,
    transformations: Vec<StatusLineTransformation>,
}

/// prepare the ops for the processing of an element
impl TryFrom<Element> for StatusLineElement {
    type Error = RahmenError;
    /// build each status line element with its transformations and the tag
    fn try_from(value: Element) -> Result<Self, Self::Error> {
        let mut transformations = vec![];
        // collect the transformation ops and store their parameters
        // the case conversion to apply
        if let Some(case_conversion) = value.case_conversion {
            transformations.push(StatusLineTransformation::ChangeCase(
                str_to_case(case_conversion.from)?,
                str_to_case(case_conversion.to)?,
            ));
        }
        // the capitalize instruction
        if value.capitalize.unwrap_or(false) {
            transformations.push(StatusLineTransformation::Capitalize);
        }
        // iterate over the regex(es)
        for replace in value.replace.into_iter().flat_map(Vec::into_iter) {
            transformations.push(StatusLineTransformation::RegexReplace(
                Regex::new(replace.regex.as_ref())?,
                replace.replace,
            ));
        }

        // return the transformations and the tags vector
        Ok(Self {
            transformations,
            tags: value.exif_tags,
        })
    }
}

/// the status line meta data element
impl StatusLineElement {
    /// this processes each metadata tag and subordinate instructions from the config file
    fn process(&self, metadata: &Metadata) -> Option<String> {
        // metadata processor: get the metadata value of the given meta tag (self.tag, from try_from above)
        // so we have three values here, self.tag (the tag), metadata (the data for this tag),
        // and value (the processed and later transformed metadata)
        // If the current metadata tag (self.tag.iter) can be converted to some value...
        if let Some(mut value) = self
            .tags
            .iter()
            // ...get tag as string...
            .map(|f| metadata.get_tag_interpreted_string(f).ok())
            // ...if it is s/th,...
            .find(Option::is_some)
            .flatten()
        // ...process that value using the pushed transformation ops and return the transformed value
        {
            for transformation in &self.transformations {
                value = transformation.transform(value);
            }
            Some(value)
        } else {
            None
        }
    }
}

/// A status line formatter formats meta data tags according to configured elements into a string
/// and then processes that string using regexes/replacements as configured
#[derive(Debug)]
pub struct StatusLineFormatter {
    // these are the meta tag entries in the config file
    elements: Vec<StatusLineElement>,
    // these are the instructions to process the whole line
    line_transformations: Vec<StatusLineTransformation>,
    // the separator to use for the join op
    line_settings: LineSettings,
    py_postprocess_fn: Option<Py<PyAny>>,
}

impl StatusLineFormatter {
    /// Construct a new `StatusLineFormatter` from a collection of elements
    pub fn new<I: Iterator<Item = Element>, J: Iterator<Item = Replacement>>(
        // we get the arguments when we're called
        statusline_elements_iter: I,
        line_transformations_iter: J,
        py_postprocess: Option<String>,
        line_settings: LineSettings,
    ) -> RahmenResult<Self> {
        // read the metadata config entries and store them to the elements vector
        let mut elements = vec![];
        for element in statusline_elements_iter {
            elements.push(element.try_into()?);
        }
        // read the postprocessing regexes and store them to the line_transformations vector
        let mut line_transformations = vec![];
        for line_transform in line_transformations_iter {
            line_transformations.push(line_transform.try_into()?);
        }

        let py_postprocess_fn = if let Some(postprocess_path) = py_postprocess {
            Some(Python::with_gil(|py| {
                let module = py.import(postprocess_path.as_ref())?;
                module.call0("export").map(|obj| obj.into_py(py))
            })?)
        } else {
            None
        };

        // return the vector(s)
        Ok(Self {
            elements,
            line_transformations,
            line_settings,
            py_postprocess_fn,
        })
    }
    /// The postprocess function calls the python code given in the py_code entry in the config file;
    /// it takes an input (our status line) and also gets our separator to split it into
    /// the individual items so that they can be postprocessed. The python code can be changed in
    /// the config file and changes take effect when the program is restarted.
    /// The python code gets a tuple of (string_to_process, item_separator) and is currently
    /// expected to return a vector of strings.
    /// TODO: error handling does not work, still have to unwrap
    pub fn postprocess(
        code: &Py<PyAny>,
        input: &str,
        separator: &str,
    ) -> RahmenResult<Vec<String>> {
        Ok(Python::with_gil(|py| -> PyResult<Vec<String>> {
            code.call1(py, (input, separator))?.extract(py)
        })?)
    }

    /// Format the meta data from the given path (called as an adaptor to the status line formatter)
    pub fn format<P: AsRef<std::ffi::OsStr>>(&self, path: P) -> RahmenResult<String> {
        let metadata = Metadata::new_from_path(path)?;
        // iterate over the tag vector we built in the constructor, but stop when we have an
        // iterator of strings
        let mut element_iter = self
            .elements
            .iter()
            // process each metadata section (element) using the associated transformation instructions
            // empty tags (no metadata found): when hide_empty is false,
            // we will return an empty string (instead of None) to make sure all metatags are
            // added to the status line. This way, we can postprocess the status line
            // being sure that parameters stay at their position.
            .flat_map(move |element| {
                if let Some(v) = element.process(&metadata) {
                    Some(v)
                } else if self.line_settings.hide_empty {
                    None
                } else {
                    Some("".to_string())
                }
            });
        let mut status_line = match (
            // hide empty entries
            self.line_settings.hide_empty,
            // don't show duplicates
            self.line_settings.uniquify,
        ) {
            (true, true) => element_iter
                // remove empty strings (which may be the result of a transformation regex replacement)
                .filter(|x| !x.is_empty())
                // ...remove multiples (e.g. if City and  ProvinceState are the same) and
                .unique()
                // join the strings using the separator
                .join(&self.line_settings.separator),
            (false, false) => element_iter.join(&self.line_settings.separator),
            (true, false) => element_iter
                // remove empty strings (which may be the result of a transformation regex replacement)
                .filter(|x| !x.is_empty())
                // join the strings using the separator
                .join(&self.line_settings.separator),
            (false, true) => element_iter.unique().join(&self.line_settings.separator),
        };
        // apply the line_transformations to the status line
        status_line = self
            .line_transformations
            .iter()
            .fold(status_line, |sl, t| t.transform(sl));
        // postprocess the status line using a python function defined in the config file (if it exists)
        Ok(if let Some(c) = &self.py_postprocess_fn {
            // postprocess gives Vec<String>, so we have to join again, but can process before
            // TODO why do I need the prefix here?
            StatusLineFormatter::postprocess(c, &status_line, &self.line_settings.separator)
                // TODO why does using a ? here gobble the error and keeps running?
                .unwrap()
                .iter()
                // finally, remove duplicates and empties unconditionally
                .filter(|x| !x.is_empty())
                .unique()
                .join(&self.line_settings.separator)
        } else {
            status_line
        })
    }
}
