extern crate exif;
#[cfg(feature = "fltk")]
extern crate fltk;
extern crate glob;
extern crate image;
#[macro_use]
extern crate lazy_static;
extern crate memmap;
extern crate mozjpeg;
extern crate reverse_geocoder;

use std::time::{Duration, Instant};

pub mod display;
#[cfg(feature = "fltk")]
pub mod display_fltk;
pub mod display_framebuffer;
pub mod errors;
pub mod provider;
pub mod provider_glob;
pub mod provider_list;

pub(crate) struct Timer<F: Fn(Duration)> {
    start: Instant,
    f: F,
}

impl<F: Fn(Duration)> Timer<F> {
    pub(crate) fn new(f: F) -> Self {
        Self {
            start: Instant::now(),
            f,
        }
    }
}

impl<F: Fn(Duration)> Drop for Timer<F> {
    fn drop(&mut self) {
        (self.f)(self.start.elapsed())
    }
}
