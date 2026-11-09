use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::menu::{MenuBuilder, SubmenuBuilder};
use tauri::{Emitter, Manager, WebviewUrl, WebviewWindowBuilder};

struct Backend {
    child: Mutex<Child>,
    input: Mutex<ChildStdin>,
}

struct CloseGuard(AtomicBool);

#[tauri::command]
fn set_close_guard(active: bool, guard: tauri::State<'_, CloseGuard>) {
    guard.0.store(active, Ordering::SeqCst);
}

#[tauri::command]
fn confirm_close(window: tauri::Window, guard: tauri::State<'_, CloseGuard>) -> Result<(), String> {
    guard.0.store(false, Ordering::SeqCst);
    window.destroy().map_err(|error| error.to_string())
}

#[tauri::command]
fn send_backend(message: String, backend: tauri::State<'_, Backend>) -> Result<(), String> {
    if message.len() > 65536 || !message.ends_with('\n') {
        return Err("Invalid backend message".into());
    }
    backend
        .input
        .lock()
        .map_err(|_| "Backend input unavailable")?
        .write_all(message.as_bytes())
        .map_err(|error| error.to_string())
}

fn start_backend(app: &tauri::AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let project = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let python = if cfg!(windows) { ".venv/Scripts/python.exe" } else { ".venv/bin/python" };
    let mut child = Command::new(project.join(python))
        .arg("-m")
        .arg("backend.sidecar")
        .current_dir(&project)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()?;
    let input = child.stdin.take().ok_or("Sidecar input unavailable")?;
    let output = child.stdout.take().ok_or("Sidecar output unavailable")?;
    app.manage(Backend {
        child: Mutex::new(child),
        input: Mutex::new(input),
    });
    let handle = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(output).lines() {
            match line {
                Ok(line) => {
                    let _ = handle.emit("backend-message", line);
                }
                Err(_) => break,
            }
        }
        let _ = handle.emit(
            "backend-message",
            r#"{"event":"error","data":"Simulator process ended"}"#,
        );
    });
    Ok(())
}

fn open_tool_window(app: tauri::AppHandle, label: &str, title: &str, route: &str, size: (f64, f64), always_on_top: bool) {
    if let Some(window) = app.get_webview_window(label) {
        let _ = window.set_always_on_top(always_on_top);
        let _ = window.show();
        let _ = window.set_focus();
        return;
    }
    let mut builder = WebviewWindowBuilder::new(
        &app,
        label,
        WebviewUrl::App(format!("index.html?window={route}").into()),
    )
    .title(title)
    .inner_size(size.0, size.1)
    .min_inner_size(if always_on_top { 360.0 } else { size.0.min(680.0) }, if always_on_top { 260.0 } else { size.1.min(500.0) });
    // Only the BeamNG overlay is always-on-top: make it a frameless, transparent HUD that blends into the game.
    if always_on_top { builder = builder.always_on_top(true).decorations(false).transparent(true).shadow(false); }
    if let Err(error) = builder.build() {
        eprintln!("Could not open {title} window: {error}");
    }
}

fn open_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
        return;
    }
    if let Err(error) = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
        .title("EV Sound Lab")
        .inner_size(1280.0, 960.0)
        .min_inner_size(980.0, 600.0)
        .build()
    {
        eprintln!("Could not open the dashboard window: {error}");
    }
}

/// Startup choice: "beamng" opens only the overlay, anything else opens only the simulator dashboard.
#[tauri::command]
fn start_mode(app: tauri::AppHandle, mode: String) {
    // Windows deadlocks if a window is built inside a synchronous command, so do it on its own thread.
    std::thread::spawn(move || {
        if mode == "beamng" {
            open_tool_window(app.clone(), "beamng-overlay", "EV Sound Lab · BeamNG", "overlay", (440.0, 640.0), true);
        } else {
            open_main_window(&app);
        }
        // Close the chooser only after the real window exists, so the app never has zero windows.
        if let Some(chooser) = app.get_webview_window("chooser") {
            let _ = chooser.close();
        }
    });
}

fn main() {
    tauri::Builder::default()
        .manage(CloseGuard(AtomicBool::new(false)))
        .on_window_event(|window, event| {
            if window.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    if window.state::<CloseGuard>().0.load(Ordering::SeqCst) {
                        api.prevent_close();
                        let _ = window.emit(
                            "backend-message",
                            r#"{"event":"close-request","data":null}"#,
                        );
                    }
                }
            }
        })
        .on_menu_event(|app, event| {
            let (label, title, route, size) = match event.id().as_ref() {
                "open_telemetry" => ("telemetry", "EV Sound Lab · Telemetry", "telemetry", (840.0, 640.0)),
                "open_sound_signal" => ("sound-signal", "EV Sound Lab · Sound signal", "sound-signal", (840.0, 700.0)),
                _ => return,
            };
            let app = app.clone();
            std::thread::spawn(move || open_tool_window(app, label, title, route, size, false));
        })
        .setup(|app| {
            #[cfg(target_os = "macos")]
            let app_menu = SubmenuBuilder::new(app, "EV Sound Lab")
                .about(None)
                .separator()
                .services()
                .separator()
                .hide()
                .hide_others()
                .show_all()
                .separator()
                .quit()
                .build()?;
            let view = SubmenuBuilder::new(app, "View")
                .text("open_telemetry", "Telemetry")
                .text("open_sound_signal", "Sound signal")
                .build()?;
            let menu_builder = MenuBuilder::new(app);
            #[cfg(target_os = "macos")]
            let menu_builder = menu_builder.item(&app_menu);
            let menu = menu_builder.item(&view).build()?;
            app.set_menu(menu)?;
            start_backend(app.handle())?;
            WebviewWindowBuilder::new(app, "chooser", WebviewUrl::App("index.html?window=chooser".into()))
                .title("EV Sound Lab")
                .inner_size(460.0, 300.0)
                .resizable(false)
                .center()
                .build()?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            send_backend,
            set_close_guard,
            confirm_close,
            start_mode
        ])
        .build(tauri::generate_context!())
        .expect("Could not start EV Sound Lab")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(backend) = app.try_state::<Backend>() {
                    if let Ok(mut input) = backend.input.lock() {
                        let _ =
                            input.write_all(b"{\"id\":0,\"command\":\"quit\",\"payload\":{}}\n");
                    }
                    if let Ok(mut child) = backend.child.lock() {
                        let deadline = Instant::now() + Duration::from_secs(3);
                        while Instant::now() < deadline {
                            if child.try_wait().ok().flatten().is_some() {
                                return;
                            }
                            std::thread::sleep(Duration::from_millis(50));
                        }
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        });
}
