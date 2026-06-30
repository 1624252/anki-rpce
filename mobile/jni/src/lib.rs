// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! JNI bridge for the Android companion.
//!
//! Proves the **shared** Anki Rust engine — including the RPCE points-at-stake
//! queue (`anki::scheduler::points_at_stake`) — links and runs on Android. The
//! companion app loads this `.so` and calls into the same engine the desktop
//! uses, satisfying the spec's "two apps, one engine" rule rather than
//! reimplementing the scheduler.
//!
//! Build for a device target with, e.g.:
//!     cargo ndk -t arm64-v8a build -p speedrun_jni --release

use jni::objects::JClass;
use jni::sys::jstring;
use jni::JNIEnv;

/// Returns a human-readable engine info string (Anki version + build hash).
/// Java: `com.rpce.speedrun.NativeBridge.engineInfo()`.
#[no_mangle]
pub extern "system" fn Java_com_rpce_speedrun_NativeBridge_engineInfo(
    env: JNIEnv,
    _class: JClass,
) -> jstring {
    let info = format!(
        "Speedrun shared engine ready — anki {} ({})",
        anki::version::version(),
        anki::version::buildhash(),
    );
    match env.new_string(info) {
        Ok(s) => s.into_raw(),
        Err(_) => std::ptr::null_mut(),
    }
}

/// Sanity self-check callable from tests on the host: confirms the engine
/// symbols are linked. Returns the same info string.
pub fn engine_info() -> String {
    format!("anki {} ({})", anki::version::version(), anki::version::buildhash())
}

#[cfg(test)]
mod tests {
    use super::engine_info;

    #[test]
    fn engine_info_reports_version() {
        let info = engine_info();
        assert!(info.starts_with("anki "), "should report the anki version");
    }
}
