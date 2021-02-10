# Rahmen: A lightweight image presenter

Rah·men [[ˈʁaːmən]](https://de.wiktionary.org/wiki/Rahmen) German: frame

Rahmen is a lightweight tool to present a slideshow of one or more JPEG images while consuming little resources. It takes a list of files or
a pattern, and periodically shows the next image. It's work in progress, but the code found here should work.

If you'd prefer a random image order, use the `shuf` command on a file list.

Below the image, some information gathered from the image's metadata will be shown.
This feature has to be configured in the `rahmen.toml` configuration file. There, you can enter
one ore more metadata tags name known to the [exiv2](https://exiv2.org/metadata.html) library
to be displayed in the information line.

Also, you can enter tuples of [regular expressions and replacements](https://docs.rs/regex/) that will be applied to the metadata.
If you set the capitalize option to `true` then the metadata content will be transformed to Title Case
before the regular expression(s) (if any) will be applied.

See the example configuration file `rahmen.toml` for some examples.

If the data is not found, per default, nothing is displayed. If the same metadata value is encountered more than once (e.g., when
City and ProvinceState are identical), it will (per default) be displayed only once to save space. This happens after the data gets
processed further (e.g. capitalized or transformed by regular expressions).

All the information items will be displayed on one line, with `", "` as (default) separator. If this line is too long for the screen, some text will overflow and
not be shown at the end of the line. Use a wider screen or a narrower font to reduce the probability that this will
happen.

The font size is configurable using the `--font_size` argument or the configuration file.

Rahmen is designed to run on low-power devices, such as the Raspberry Pi 1 (in fact it was specifically created to 
build a digital picture frame out of an old monitor and an old Raspberry Pi 1 due to the lack of 
capable software). While it is not heavily optimized to consume
little resources, some effort has been put into loading, pre-processing and rendering images.

## Dependencies

Rahmen depends on various libraries, which should be available on most Linux distributions. Specifically, it needs:

* `libgexiv2-dev`

Rahmen will run if there's no configuration file, but will use minimal defaults (see below).

## Building

`cargo build --bin rahmen`

## Running

```shell
./rahmen --help`
Rahmen client

USAGE:
rahmen [OPTIONS] <input>

ARGS:
<input>

FLAGS:
-h, --help       Prints help information
-V, --version    Prints version information

OPTIONS:
--buffer_max_size <buffer_max_size>    [default: 16000000]
```

The buffer size (in Bytes) determines the downscaling of images. All images that are larger than the buffer size in
Bytes will be scaled down to the buffer size. This should be larger than your monitor to avoid scaling
artefacts/jaggies.

Rule of thumb: `long side of the monitor ^ 2 * 2`, e.g. for a 1600 * 1200 monitor: `1600 * 1600 * 2 = 5120000`.

(Images smaller than your monitor will be scaled up to the monitor size and will possibly appear blurred. Avoid them if
you don't like this.)

```shell
-d, --display <display>
Select the display provider [default: framebuffer] [possible values: framebuffer]
```

(If compiled with the FLTK option, the FLTK display provider will also be available, use `fltk` as value.)

```shell
        --font_size <font_size>                
```
The font size to use in px.
```shell
        --font <font>
            [default: /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf]
```
Rahmen will display information from the image's metadata (see above) in a single line below
the image in the given font. If the font is not found, the program exits. If you don't want to install lots of fonts,
just point this option to a TrueType font file.

```shell
    -o, --output <output>                      
    -t, --time <time>                          [default: 90]
```

The output points to the frame buffer to be used. Usually `/dev/fb0`.

The time (in seconds) defines the interval to change to the next slide. On the Raspberry Pi version 1, it takes several
seconds to scale larger images. If the time given is shorter than what it takes to display the image, no images will be
skipped, the image will be displayed to the next full second after it is fully loaded plus the time it takes to load the
next image. So on low-resource systems this should not be set too short, otherwise if the next image is very small, it
could lead to the image displaying for less than 1 second.

```shell
    -c, --config <config file>
```
Indicate the name and path of the configuration file to read. This takes precedence.

###Shell script

We have added a basic bash script (in the ``utils`` directory) which creates a random image list from a 
given folder and starts ``rahmen``. You could configure the machine to use autologin and call this script from the end of your
``.bashrc`` to start a ``rahmen`` slideshow automatically after the system has started up. Of course, be sure
to change to folders and paths to match your setup.

## Configuration File (default name: rahmen.toml)

Rahmen will run without configuration file using the default settings given above, but no metadata will be
displayed below the image. To show metadata, a configuration file must be used; an example
file (`rahmen.toml`) can be found among the sources.

The default lookup paths for the configuration file are either `~/.config/rahmen.toml` or `/etc/rahmen.toml`.
If both are present, the file in the home directory takes precedence.

The configuration file has to be written in TOML and takes the following instructions: 

```
font_size = 24
delay = 90
```
Values for font size (px) and the interval before the next image (in s, see above, --time parameter).
If command line parameters are given, they take precedence over the values in this file.

### Metadata
```toml
[[status_line]]
exif_tags = ["Iptc.Application2.ObjectName"]
```
Each `[[status_line]]` entry can contain one 

`exif-tags = ["Some.Tag.Known.to.Exiv2"]`

entry, and optionally, one

`replace = [{ regex = 'regex1', replace = 'repl1' }, { regex = '...', replace = '...' }, ... ]` 

entry, where one or more regular expressions and the replacements for the part they match could be supplied.
The regular expression operations will be applied one after the other in the given order.
For long expressions, or if you wish to comment them, this could also be written like
```toml
[[status_line.replace]]
# get named fields of the date
regex = '(?P<y>\d{4})[-:]0*(?P<M>\d+)[-:]0*(?P<d>\d+)\s+0*(?P<h>\d+:)0*(?P<m>\d+):(?P<s>\d{2})'
## with time
## replace = '$d.$M.$y, $h$m'
# without time
replace = '$d.$M.$y'
```
The [tag names that can be used are listed on the this exiv2 webpage](https://exiv2.org/metadata.html).
This doesn't mean that all these are actually present in your image file. Use [exiftool](https://exiftool.org/)
to show you the metadata in your file and see what is available.

Because some of the tags we used were in ALL-CAPS which doesn't look nice, we offer case conversions that you can apply
to the data before they are processed by the regular expressions described above. The order in the configuration file
doesn't matter here. The [available case strings can be found here.](https://github.com/rutrum/convert-case#cases) 
See the following example. The previous method of setting the `capitalize` variable is also still available.
```toml
# convert input from UPPER CASE to Title Case 
case_conversion = { from = 'Upper', to = 'Title' }
# this does the same, but only from UPPER to Title Case
capitalize = true
```
Post-processing the metadata line: Optionally, the metadata line can be processed after it has been assembled
from the tags described above. This can be finely controlled using the following settings:
```toml
separator = "|"
uniquify = false
hide_empty = false
```
That way it's possible to set a custom separator, and to display multiple identical and/or empty tags, too
(the defaults are `", "` for the separator and `false` for both other values.)

Then, you can apply regular expressions to the whole line, in the same way described above for the
individual tags. But you'll have to take care of removing empty entries (if not set to hide)
(resulting in superfluous separators) and take care of deduplication
(if disabled) by yourself. This creates a way to format metadata items in the text bar relative to other metadata.
```toml
line_replacements = [
    {regex = '(?P<text>^.*), (?P<subloc>.*), (?P<loc>.*), (?P<province>Mark), (?P<rest>.*$)', replace = '$text, $subloc ($province), $rest'},
    {regex = '(?P<text>^.*), (?P<subloc>.*), (?P<loc>.*), (?P<province>.*), (?P<country>Südkorea), (?P<rest>.*$)', replace = '$text, $loc, $province, $country, $rest'},
    {regex = '(?P<text>^.*), (?P<sublocation>.*), (?P<location>.*), (?P<province>.*), (?P<country>Morocco), (?P<rest>.*$)',replace = '$text, $sublocation, $location, $country, $rest'},
    #zap empty commas from the separator
    {regex = '^, ', replace = ','},
    {regex = '^[ ,]', replace = ''},
]
```

The human-readable location tags in the enclosed `rahmen.toml` example file are based on the information
you can tell Adobe Lightroom to add when it finds a GPS location in the image metadata.

[The regular expressions and replacements are documented here.](https://docs.rs/regex/) 

##Bugs, Issues, Desiderata

- The font rendering is not really beautiful and sometimes, glyphs overlap.
- The overflowing text is just not displayed.
- The text bar might look better centered.


## Cross-compiling for the Raspberry Pi 1

Cross-compilation is a mess. The instructions below wokred until we decided to include a dependency on `libgexiv2` to
extract image metadata. It has some trouble cross-compiling and eventually, we gave up on it. Currently, we build Rahmen
on a Raspberry Pi 4, and cross-compile to ARMv6 on this platform---it works, although it's still a hack. At least
compilation times are less than "a night."

Preparation:

1. Add the Rust toolchain:
   ```
   rustup target add arm-unknown-linux-gnueabihf
   ```

2. Setup the GCC toolchain. The first-generation Raspberry Pi had a BCM2835, supporting the ARMv6 instruction set.
   Current ARM compilers on Debian only support armv7. For this reason, we need to use a different toolchain, for
   example the one provided specifically for the Raspberry Pi
   on [github.com/raspberrypi/tools](https://github.com/raspberrypi/tools). Export its `bin` directory to the local
   path.

   Tell Cargo to use the correct cross-compiler by adding the following content to `~/.cargo/config.toml`
   or `.cargo/config.toml` in the project directory:

   ```toml
   [target.arm-unknown-linux-gnueabihf]
   linker = "arm-linux-gnueabihf-gcc"
   ar = "arm-linux-gnueabihf-ar"
   ```

   Add the toolchain to the current environment by adding it to the path:

   ```shell
   git clone https://github.com/raspberrypi/tools
   export PATH="$PATH:$(pwd)/tools/arm-bcm2708/arm-linux-gnueabihf/bin/"
   ```

3. Add the `armhf` target to Debian and install a dependency:

   ```shell
   dpkg --add-architecture armhf
   apt install libgexiv2-dev:armhf libfontconfig1-dev:armhf
   ```

Now, issue the following command to cross-compile the binary.

```shell
cargo build --target arm-unknown-linux-gnueabihf --bin rahmen \
  --release
```

If the build fails in `font-kit` with a message that the C compiler cannot produce executables, try to force CC and AR
using the following command line:

```shell
AR=arm-linux-gnueabihf-ar CC=arm-linux-gnueabihf-gcc cargo build \
  --target arm-unknown-linux-gnueabihf --bin rahmen \
  --release --no-default-features
```

Find the binary in `target/arm-unknown-linux-gnueabihf/release/rahmen`

### Stripping the binary

The binary includes debug symbols, which consume a rather large amount of space. The `strip` tool can be used to remove
the debug symbols from the binary:

`arm-linux-gnueabihf-strip target/arm-unknown-linux-gnueabihf/release/rahmen`

## FLTK support

The FLTK renders a window on various platforms, which can be used for development.

The feature `fltk` is not enabled by default. Pass `--features fltk` to `cargo build` to enable.
