use std::time::Duration;
use tokio::time::sleep;
use serde::Deserialize;
use anyhow::Result;
use chrono::Timelike;
use std::sync::atomic::{AtomicBool, Ordering};

#[derive(Debug, Deserialize)]
struct HabitStatus {
    user_id: i64,
    today_record: Record,
}

#[derive(Debug, Deserialize)]
struct Record {
    wake_time: Option<String>,
    bath_time: Option<String>,
}

const BACKEND_URL: &str = "http://localhost:8000"; 
const USER_ID: i64 = 1; 

static SHOULD_LOCK: AtomicBool = AtomicBool::new(false);

async fn check_habit_status() -> Result<bool> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build()?;
    let url = format!("{}/status/{}", BACKEND_URL, USER_ID);
    
    let resp = client.get(&url).send().await?;
    if resp.status().is_success() {
        let status: HabitStatus = resp.json().await?;
        let now = chrono::Local::now();
        let hour = now.hour();
        
        if hour >= 9 && hour < 23 {
            return Ok(status.today_record.wake_time.is_some());
        } else if hour >= 23 || hour < 4 { // Night time
            return Ok(status.today_record.bath_time.is_some());
        }
        return Ok(true); 
    }
    Err(anyhow::anyhow!("Failed to fetch status: {}", resp.status()))
}

#[cfg(windows)]
mod windows_lock {
    use windows::Win32::UI::WindowsAndMessaging::*;
    use windows::Win32::Foundation::*;
    use windows::Win32::Graphics::Gdi::*;
    use windows::core::PCWSTR;
    use std::sync::atomic::Ordering;
    use super::SHOULD_LOCK;

    pub unsafe extern "system" fn window_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
        match msg {
            WM_PAINT => {
                let mut ps = PAINTSTRUCT::default();
                let hdc = BeginPaint(hwnd, &mut ps);
                let mut rect = RECT::default();
                GetClientRect(hwnd, &mut rect);
                
                SetBkMode(hdc, TRANSPARENT);
                SetTextColor(hdc, COLORREF(0x0000FF)); // Red text
                
                // DrawTextW using explicit PCWSTR pointer and 5 arguments.
                let text: Vec<u16> = "HABIT MISSION NOT ACCOMPLISHED\nPLEASE CHECK IN VIA LINE BOT\0".encode_utf16().collect();
                
                DrawTextW(
                    hdc, 
                    PCWSTR(text.as_ptr()),
                    -1_i32,
                    &mut rect, 
                    DRAW_TEXT_FORMAT(37) // DT_CENTER | DT_VCENTER | DT_SINGLELINE
                );
                
                EndPaint(hwnd, &ps);
                LRESULT(0)
            }
            WM_DESTROY => {
                PostQuitMessage(0);
                LRESULT(0)
            }
            _ => DefWindowProcW(hwnd, msg, wparam, lparam),
        }
    }

    pub fn start_lock_window() {
        std::thread::spawn(|| unsafe {
            let instance = GetModuleHandleW(None).unwrap();
            let class_name = windows::core::w!("GachiGachiLocker");

            let wc = WNDCLASSW {
                lpfnWndProc: Some(window_proc),
                hInstance: instance,
                lpszClassName: class_name,
                ..Default::default()
            };

            RegisterClassW(&wc);

            let screen_width = GetSystemMetrics(SM_CXSCREEN);
            let screen_height = GetSystemMetrics(SM_CYSCREEN);

            let hwnd = CreateWindowExW(
                WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT,
                class_name,
                windows::core::w!("Locker"),
                WS_POPUP,
                0, 0, screen_width, screen_height,
                None, None, instance, None,
            );

            SetLayeredWindowAttributes(hwnd, COLORREF(0), 180, LWA_ALPHA);
            ShowWindow(hwnd, SW_SHOW);

            let mut msg = MSG::default();
            while GetMessageW(&mut msg, None, 0, 0).into() {
                if !SHOULD_LOCK.load(Ordering::SeqCst) {
                    ShowWindow(hwnd, SW_HIDE);
                } else {
                    ShowWindow(hwnd, SW_SHOW);
                    SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE);
                }
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
        });
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    println!("Habit Locker Gachi-Gachi Agent Starting...");
    
    #[cfg(windows)]
    windows_lock::start_lock_window();

    loop {
        match check_habit_status().await {
            Ok(is_accomplished) => {
                if !is_accomplished {
                    SHOULD_LOCK.store(true, Ordering::SeqCst);
                    println!("!!! MISSION NOT ACCOMPLISHED !!!");
                } else {
                    SHOULD_LOCK.store(false, Ordering::SeqCst);
                    println!("Mission accomplished. Relax.");
                }
            }
            Err(e) => {
                eprintln!("Status Check Error: {}", e);
            }
        }
        
        sleep(Duration::from_secs(30)).await;
    }
}
