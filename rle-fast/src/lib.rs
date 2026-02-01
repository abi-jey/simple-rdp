//! Fast RLE bitmap decompression for RDP.
//!
//! Implements decompression for RLE-compressed bitmaps as specified in
//! MS-RDPBCGR section 2.2.9.1.1.3.1.2.4 and section 3.1.9.
//!
//! This releases the GIL during decompression so it doesn't block
//! the Python asyncio event loop.

use pyo3::prelude::*;
use pyo3::types::PyBytes;

// RLE compression order codes
// Regular codes (extracted from high 3 bits)
const REGULAR_BG_RUN: u8 = 0x0;
const REGULAR_FG_RUN: u8 = 0x1;
const REGULAR_FGBG_IMAGE: u8 = 0x2;
const REGULAR_COLOR_RUN: u8 = 0x3;
const REGULAR_COLOR_IMAGE: u8 = 0x4;

// Lite codes (extracted from high 4 bits)
const LITE_SET_FG_FG_RUN: u8 = 0xC;
const LITE_SET_FG_FGBG_IMAGE: u8 = 0xD;
const LITE_DITHERED_RUN: u8 = 0xE;

// Mega-mega codes (full byte value >= 0xF0)
const MEGA_MEGA_BG_RUN: u8 = 0xF0;
const MEGA_MEGA_FG_RUN: u8 = 0xF1;
const MEGA_MEGA_FGBG_IMAGE: u8 = 0xF2;
const MEGA_MEGA_COLOR_RUN: u8 = 0xF3;
const MEGA_MEGA_COLOR_IMAGE: u8 = 0xF4;
const MEGA_MEGA_SET_FG_RUN: u8 = 0xF6;
const MEGA_MEGA_SET_FGBG_IMAGE: u8 = 0xF7;
const MEGA_MEGA_DITHERED_RUN: u8 = 0xF8;

// Special codes
const SPECIAL_FGBG_1: u8 = 0xF9;
const SPECIAL_FGBG_2: u8 = 0xFA;
const WHITE: u8 = 0xFD;
const BLACK: u8 = 0xFE;

// Masks
const MASK_REGULAR_RUN_LENGTH: u8 = 0x1F; // 5 bits for regular orders
const MASK_LITE_RUN_LENGTH: u8 = 0x0F;    // 4 bits for lite orders

/// RLE decompression state machine
struct RleDecoder<'a> {
    src: &'a [u8],
    src_pos: usize,
    output: Vec<u8>,
    dest_pos: usize,
    pixel_in_row: usize,
    bytes_per_pixel: usize,
    width: usize,
    row_delta: usize,
    row_padding: usize,
    fg_pel: Vec<u8>,
    first_line: bool,
    insert_fg_pel: bool,
}

impl<'a> RleDecoder<'a> {
    fn new(
        compressed_data: &'a [u8],
        width: usize,
        height: usize,
        bpp: usize,
        has_header: bool,
    ) -> Self {
        let bytes_per_pixel = match bpp {
            8 => 1,
            15 | 16 => 2,
            24 => 3,
            _ => 3,
        };

        // Parse compression header if present
        let src = if has_header && compressed_data.len() >= 8 {
            let cb_comp_main_body_size =
                u16::from_le_bytes([compressed_data[2], compressed_data[3]]) as usize;
            let end = std::cmp::min(8 + cb_comp_main_body_size, compressed_data.len());
            &compressed_data[8..end]
        } else {
            compressed_data
        };

        // Calculate row delta (scanline width in bytes, padded to 4-byte boundary)
        let actual_row_bytes = width * bytes_per_pixel;
        let row_delta = if actual_row_bytes % 4 != 0 {
            actual_row_bytes + (4 - actual_row_bytes % 4)
        } else {
            actual_row_bytes
        };
        let row_padding = row_delta - actual_row_bytes;

        // Initialize output buffer (with row padding)
        let output = vec![0u8; height * row_delta];

        // Default foreground pixel (white)
        let fg_pel = vec![0xFF; bytes_per_pixel];

        RleDecoder {
            src,
            src_pos: 0,
            output,
            dest_pos: 0,
            pixel_in_row: 0,
            bytes_per_pixel,
            width,
            row_delta,
            row_padding,
            fg_pel,
            first_line: true,
            insert_fg_pel: false,
        }
    }

    #[inline(always)]
    fn read_byte(&mut self) -> u8 {
        if self.src_pos < self.src.len() {
            let b = self.src[self.src_pos];
            self.src_pos += 1;
            b
        } else {
            0
        }
    }

    #[inline(always)]
    fn read_pixel(&mut self) -> Vec<u8> {
        let bpp = self.bytes_per_pixel;
        if self.src_pos + bpp <= self.src.len() {
            let pixel = self.src[self.src_pos..self.src_pos + bpp].to_vec();
            self.src_pos += bpp;
            pixel
        } else {
            vec![0; bpp]
        }
    }

    #[inline(always)]
    fn write_pixel(&mut self, pixel: &[u8]) {
        let bpp = self.bytes_per_pixel;
        if self.dest_pos + bpp <= self.output.len() {
            self.output[self.dest_pos..self.dest_pos + bpp].copy_from_slice(&pixel[..bpp]);
            self.dest_pos += bpp;
            self.pixel_in_row += 1;

            // Skip row padding when we reach end of row
            if self.pixel_in_row >= self.width {
                self.dest_pos += self.row_padding;
                self.pixel_in_row = 0;
            }
        }
    }

    #[inline(always)]
    fn get_prev_row_pixel(&self) -> Vec<u8> {
        let bpp = self.bytes_per_pixel;
        if self.dest_pos >= self.row_delta {
            let prev_pos = self.dest_pos - self.row_delta;
            if prev_pos + bpp <= self.output.len() {
                return self.output[prev_pos..prev_pos + bpp].to_vec();
            }
        }
        vec![0; bpp]
    }

    #[inline(always)]
    fn xor_pixels(&self, a: &[u8], b: &[u8]) -> Vec<u8> {
        a.iter().zip(b.iter()).map(|(x, y)| x ^ y).collect()
    }

    #[inline(always)]
    fn write_bg_pixel(&mut self) {
        if self.first_line {
            let zero_pixel = vec![0u8; self.bytes_per_pixel];
            self.write_pixel(&zero_pixel);
        } else {
            let prev = self.get_prev_row_pixel();
            self.write_pixel(&prev);
        }
    }

    #[inline(always)]
    fn write_fg_pixel(&mut self) {
        if self.first_line {
            let fg = self.fg_pel.clone();
            self.write_pixel(&fg);
        } else {
            let prev = self.get_prev_row_pixel();
            let xored = self.xor_pixels(&prev, &self.fg_pel);
            self.write_pixel(&xored);
        }
    }

    fn decompress(&mut self) -> Vec<u8> {
        let src_end = self.src.len();
        let output_len = self.output.len();

        while self.src_pos < src_end && self.dest_pos < output_len {
            // Check if we've finished the first line
            if self.first_line && self.dest_pos >= self.row_delta {
                self.first_line = false;
                self.insert_fg_pel = false;
            }

            let order_header = self.read_byte();

            // Handle special/mega codes (>= 0xF0)
            if order_header >= 0xF0 {
                self.insert_fg_pel = false;
                self.process_mega_code(order_header);
                continue;
            }

            // Handle Lite codes (bytes 0xC0-0xEF have 4-bit code in high nibble)
            if order_header >= 0xC0 {
                self.insert_fg_pel = false;
                self.process_lite_code(order_header);
                continue;
            }

            // Regular codes (bytes 0x00-0xBF have 3-bit code in high 3 bits)
            self.process_regular_code(order_header);
        }

        // Strip row padding and return actual bitmap data
        self.extract_result()
    }

    fn process_mega_code(&mut self, order_header: u8) {
        match order_header {
            WHITE => {
                let white_pixel = vec![0xFF; self.bytes_per_pixel];
                self.write_pixel(&white_pixel);
            }
            BLACK => {
                let black_pixel = vec![0x00; self.bytes_per_pixel];
                self.write_pixel(&black_pixel);
            }
            SPECIAL_FGBG_1 => {
                self.process_fgbg_bitmask(0x03, 8);
            }
            SPECIAL_FGBG_2 => {
                self.process_fgbg_bitmask(0x05, 8);
            }
            MEGA_MEGA_BG_RUN => {
                let run_length = self.read_u16() as usize;
                for _ in 0..run_length {
                    self.write_bg_pixel();
                }
            }
            MEGA_MEGA_FG_RUN => {
                let run_length = self.read_u16() as usize;
                for _ in 0..run_length {
                    self.write_fg_pixel();
                }
            }
            MEGA_MEGA_SET_FG_RUN => {
                let run_length = self.read_u16() as usize;
                self.fg_pel = self.read_pixel();
                for _ in 0..run_length {
                    self.write_fg_pixel();
                }
            }
            MEGA_MEGA_DITHERED_RUN => {
                let run_length = self.read_u16() as usize;
                let pixel_a = self.read_pixel();
                let pixel_b = self.read_pixel();
                for _ in 0..run_length {
                    self.write_pixel(&pixel_a);
                    self.write_pixel(&pixel_b);
                }
            }
            MEGA_MEGA_COLOR_RUN => {
                let run_length = self.read_u16() as usize;
                let color = self.read_pixel();
                for _ in 0..run_length {
                    self.write_pixel(&color);
                }
            }
            MEGA_MEGA_FGBG_IMAGE => {
                let run_length = self.read_u16() as usize;
                self.process_fgbg_image(run_length);
            }
            MEGA_MEGA_SET_FGBG_IMAGE => {
                let run_length = self.read_u16() as usize;
                self.fg_pel = self.read_pixel();
                self.process_fgbg_image(run_length);
            }
            MEGA_MEGA_COLOR_IMAGE => {
                let run_length = self.read_u16() as usize;
                for _ in 0..run_length {
                    let pixel = self.read_pixel();
                    self.write_pixel(&pixel);
                }
            }
            _ => {}
        }
    }

    fn process_lite_code(&mut self, order_header: u8) {
        let code = order_header >> 4;

        match code {
            LITE_SET_FG_FG_RUN => {
                let mut run_length = (order_header & MASK_LITE_RUN_LENGTH) as usize;
                if run_length == 0 {
                    run_length = self.read_byte() as usize + 16;
                }
                self.fg_pel = self.read_pixel();
                for _ in 0..run_length {
                    self.write_fg_pixel();
                }
            }
            LITE_SET_FG_FGBG_IMAGE => {
                let mut run_length = (order_header & MASK_LITE_RUN_LENGTH) as usize;
                if run_length == 0 {
                    run_length = self.read_byte() as usize + 1;
                } else {
                    run_length *= 8;
                }
                self.fg_pel = self.read_pixel();
                self.process_fgbg_image(run_length);
            }
            LITE_DITHERED_RUN => {
                let mut run_length = (order_header & MASK_LITE_RUN_LENGTH) as usize;
                if run_length == 0 {
                    run_length = self.read_byte() as usize + 16;
                }
                let pixel_a = self.read_pixel();
                let pixel_b = self.read_pixel();
                for _ in 0..run_length {
                    self.write_pixel(&pixel_a);
                    self.write_pixel(&pixel_b);
                }
            }
            _ => {}
        }
    }

    fn process_regular_code(&mut self, order_header: u8) {
        let code = order_header >> 5;

        match code {
            REGULAR_BG_RUN => {
                let mut run_length = (order_header & MASK_REGULAR_RUN_LENGTH) as usize;
                if run_length == 0 {
                    run_length = self.read_byte() as usize + 32;
                }
                // Handle insert_fg_pel flag for BG run continuation
                if self.insert_fg_pel {
                    self.write_fg_pixel();
                    run_length = run_length.saturating_sub(1);
                }
                for _ in 0..run_length {
                    self.write_bg_pixel();
                }
                self.insert_fg_pel = true;
            }
            REGULAR_FG_RUN => {
                self.insert_fg_pel = false;
                let mut run_length = (order_header & MASK_REGULAR_RUN_LENGTH) as usize;
                if run_length == 0 {
                    run_length = self.read_byte() as usize + 32;
                }
                for _ in 0..run_length {
                    self.write_fg_pixel();
                }
            }
            REGULAR_FGBG_IMAGE => {
                self.insert_fg_pel = false;
                let mut run_length = (order_header & MASK_REGULAR_RUN_LENGTH) as usize;
                if run_length == 0 {
                    run_length = self.read_byte() as usize + 1;
                } else {
                    run_length *= 8;
                }
                self.process_fgbg_image(run_length);
            }
            REGULAR_COLOR_RUN => {
                self.insert_fg_pel = false;
                let mut run_length = (order_header & MASK_REGULAR_RUN_LENGTH) as usize;
                if run_length == 0 {
                    run_length = self.read_byte() as usize + 32;
                }
                let color = self.read_pixel();
                for _ in 0..run_length {
                    self.write_pixel(&color);
                }
            }
            REGULAR_COLOR_IMAGE => {
                self.insert_fg_pel = false;
                let mut run_length = (order_header & MASK_REGULAR_RUN_LENGTH) as usize;
                if run_length == 0 {
                    run_length = self.read_byte() as usize + 32;
                }
                for _ in 0..run_length {
                    let pixel = self.read_pixel();
                    self.write_pixel(&pixel);
                }
            }
            _ => {
                self.insert_fg_pel = false;
            }
        }
    }

    #[inline(always)]
    fn read_u16(&mut self) -> u16 {
        let lo = self.read_byte() as u16;
        let hi = self.read_byte() as u16;
        lo | (hi << 8)
    }

    fn process_fgbg_bitmask(&mut self, bitmask: u8, count: usize) {
        for i in 0..count {
            if bitmask & (1 << i) != 0 {
                self.write_fg_pixel();
            } else {
                self.write_bg_pixel();
            }
        }
    }

    fn process_fgbg_image(&mut self, run_length: usize) {
        let mut bitmask: u8 = 0;
        for i in 0..run_length {
            if i % 8 == 0 {
                bitmask = self.read_byte();
            }
            if bitmask & (1 << (i % 8)) != 0 {
                self.write_fg_pixel();
            } else {
                self.write_bg_pixel();
            }
        }
    }

    fn extract_result(&self) -> Vec<u8> {
        let actual_row_bytes = self.width * self.bytes_per_pixel;
        let height = self.output.len() / self.row_delta;
        let mut result = Vec::with_capacity(height * actual_row_bytes);

        for y in 0..height {
            let row_start = y * self.row_delta;
            let row_end = row_start + actual_row_bytes;
            if row_end <= self.output.len() {
                result.extend_from_slice(&self.output[row_start..row_end]);
            }
        }

        result
    }
}

/// Decompress RLE-compressed bitmap data.
///
/// This function releases the GIL during decompression so it doesn't block
/// the Python asyncio event loop when called from a thread pool.
///
/// Args:
///     compressed_data: The compressed bitmap data (including optional header)
///     width: Width of the bitmap in pixels
///     height: Height of the bitmap in pixels
///     bpp: Bits per pixel (8, 15, 16, or 24)
///     has_header: Whether the data includes a TS_CD_HEADER (8 bytes)
///
/// Returns:
///     Decompressed bitmap data as bytes
#[pyfunction]
#[pyo3(signature = (compressed_data, width, height, bpp, has_header=true))]
fn decompress_rle<'py>(
    py: Python<'py>,
    compressed_data: &[u8],
    width: usize,
    height: usize,
    bpp: usize,
    has_header: bool,
) -> PyResult<Bound<'py, PyBytes>> {
    // Copy input data so we can release the GIL
    let input_copy = compressed_data.to_vec();

    // Release the GIL during heavy computation
    // This allows the asyncio event loop to continue processing
    let result = py.allow_threads(|| {
        let mut decoder = RleDecoder::new(&input_copy, width, height, bpp, has_header);
        decoder.decompress()
    });

    Ok(PyBytes::new(py, &result))
}

/// Fast RLE bitmap decompression for RDP.
#[pymodule]
fn rle_fast(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(decompress_rle, m)?)?;
    Ok(())
}
