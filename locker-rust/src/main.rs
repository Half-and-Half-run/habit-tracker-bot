use std::time::Duration;
use tokio::time::sleep;
use serde::Deserialize;
use anyhow::{Result, Context};
use chrono::Timelike;

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

const BACKEND_URL: &str = "http://localhost:8000"; // Should be configurable
const USER_ID: i64 = 1; // Placeholder

async fn check_habit_status() -> Result<bool> {
    let client = reqwest::Client::new();
    let url = format!("{}/status/{}", BACKEND_URL, USER_ID);
    
    let resp = client.get(&url).send().await?;
    if resp.status().is_success() {
        let status: HabitStatus = resp.json().await?;
        // Check if current hour's deadline is met
        let now = chrono::Local::now();
        let hour = now.hour();
        
        // Simple logic:
        // 9:00 - 23:00 -> Check wake_time
        // 23:00 - 24:00 -> Check bath_time
        if hour >= 9 && hour < 23 {
            return Ok(status.today_record.wake_time.is_some());
        } else if hour >= 23 {
            return Ok(status.today_record.bath_time.is_some());
        }
        return Ok(true); // Outside of deadline hours
    }
    Err(anyhow::anyhow!("Failed to fetch status: {}", resp.status()))
}

#[cfg(windows)]
fn enforce_lock_windows() {
    // This is where the Windows-specific "tough" lock logic would go.
    // E.g., setting a full-screen topmost window, or interacting with the lock screen.
    println!("--- LOCK ENFORCED (WINDOWS) ---");
}

#[tokio::main]
async fn main() -> Result<()> {
    println!("Habit Locker Rust Agent v0.1.0 Started.");
    
    loop {
        match check_habit_status().await {
            Ok(is_accomplished) => {
                if !is_accomplished {
                    println!("Habit mission NOT accomplished! Locking system...");
                    #[cfg(windows)]
                    enforce_lock_windows();
                } else {
                    println!("Habit mission accomplished. Standing by.");
                }
            }
            Err(e) => {
                eprintln!("Error checking status (Server might be down): {}", e);
            }
        }
        
        sleep(Duration::from_secs(60)).await;
    }
}
