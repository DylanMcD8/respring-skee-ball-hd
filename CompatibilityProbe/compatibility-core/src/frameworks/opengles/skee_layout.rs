//! Legacy UI centered over an expanded 3D target.
use crate::gles::{GLES, gles11_raw as gl};
#[derive(Clone, Copy)]
pub struct Layout { pub viewport: [i32;4], pub scissor: [i32;4], pub perspective: bool }
impl Default for Layout { fn default() -> Self { Self { viewport:[0,0,768,1024], scissor:[0,0,768,1024], perspective:false } } }
fn dimensions() -> &'static std::sync::atomic::AtomicU64 {
    static SIZE: std::sync::OnceLock<std::sync::atomic::AtomicU64> = std::sync::OnceLock::new();
    SIZE.get_or_init(|| {
        let h = std::env::var("SKEEBALL_WORLD_HEIGHT").ok().and_then(|s| s.parse::<u32>().ok())
            .filter(|h| (1024..=4096).contains(h)).unwrap_or(0);
        let w = std::env::var("SKEEBALL_WORLD_WIDTH").ok().and_then(|s| s.parse::<u32>().ok())
            .filter(|w| (768..=4096).contains(w)).unwrap_or(768);
        std::sync::atomic::AtomicU64::new((u64::from(w)<<32)|u64::from(h))
    })
}
pub fn width() -> i32 { (dimensions().load(std::sync::atomic::Ordering::Relaxed)>>32) as i32 }
pub fn height() -> i32 { dimensions().load(std::sync::atomic::Ordering::Relaxed) as u32 as i32 }
pub fn update_size(w: u32, h: u32) -> bool {
    if height() == 0 || w == 0 || h == 0 { return false; }
    let fit = (w as f64 / 768.0).min(h as f64 / 1024.0);
    let nw = (w as f64 / fit).round().clamp(768.0,4096.0) as u64;
    let nh = (h as f64 / fit).round().clamp(1024.0,4096.0) as u64;
    let next = (nw<<32)|nh;
    dimensions().swap(next,std::sync::atomic::Ordering::Relaxed) != next
}
pub fn storage_width(original: i32, h: i32) -> i32 {
    if height() > 0 && original == 768 && h == 1024 { width() } else { original }
}
pub fn storage_height(width: i32, original: i32) -> i32 {
    if height() > 0 && width == 768 && original == 1024 { height() } else { original }
}
impl Layout {
    pub unsafe fn apply(&self, gles: &mut dyn GLES, scale: i32) {
        let h = height();
        if h == 0 { return; }
        let [x,y,w,vh] = self.viewport;
        if w != 768 || vh != 1024 { return; }
        let offset = (h-1024)/2;
        let wide = width();
        let offset_x = (wide-768)/2;
        if self.perspective { gles.Viewport(x*scale,y*scale,wide*scale,h*scale); }
        else { gles.Viewport((x+offset_x)*scale,(y+offset)*scale,w*scale,vh*scale); }
        let [sx,sy,sw,sh] = self.scissor;
        if self.perspective && self.scissor == [0,0,768,1024] { gles.Scissor(0,0,wide*scale,h*scale); }
        else { gles.Scissor((sx+offset_x)*scale,(sy+offset)*scale,sw*scale,sh*scale); }
    }
}
pub unsafe fn projection_mode(gles: &mut dyn GLES) -> bool {
    let mut mode=0; gles.GetIntegerv(gl::MATRIX_MODE,&mut mode); mode as u32 == gl::PROJECTION
}
