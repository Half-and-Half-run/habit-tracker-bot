package db

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"habit-tracker-bot/internal/domain"
	"github.com/jmoiron/sqlx"
	_ "modernc.org/sqlite"
)

type SQLiteRepository struct {
	db *sqlx.DB
}

func NewSQLiteRepository(dbPath string) (*SQLiteRepository, error) {
	dir := filepath.Dir(dbPath)
	if dir != "." {
		err := os.MkdirAll(dir, 0755)
		if err != nil {
			return nil, fmt.Errorf("failed to create db directory: %w", err)
		}
	}

	db, err := sqlx.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open db: %w", err)
	}

	// Wait for connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping db: %w", err)
	}

	return &SQLiteRepository{db: db}, nil
}

func (r *SQLiteRepository) InitSchema() error {
	schema := `
	CREATE TABLE IF NOT EXISTS users (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		line_user_id TEXT UNIQUE,
		created_at TEXT DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS habits (
		date TEXT,
		user_id INTEGER,
		wake_time TEXT,
		bath_time TEXT,
		wake_failed_tweeted INTEGER DEFAULT 0,
		bath_failed_tweeted INTEGER DEFAULT 0,
		PRIMARY KEY (date, user_id)
	);

	CREATE TABLE IF NOT EXISTS user_stats (
		user_id INTEGER PRIMARY KEY,
		wake_consecutive_failures INTEGER DEFAULT 0,
		bath_consecutive_failures INTEGER DEFAULT 0
	);

	CREATE TABLE IF NOT EXISTS habit_settings (
		user_id INTEGER PRIMARY KEY,
		wake_deadline INTEGER DEFAULT 540, -- 09:00
		bath_deadline INTEGER DEFAULT 1380 -- 23:00
	);
	`
	_, err := r.db.Exec(schema)
	return err
}

func (r *SQLiteRepository) GetOrRegisterUser(lineUserID string) (int64, error) {
	var userID int64
	err := r.db.Get(&userID, "SELECT id FROM users WHERE line_user_id = ?", lineUserID)
	if err == nil {
		return userID, nil
	}

	if err != sql.ErrNoRows {
		return 0, err
	}

	result, err := r.db.Exec("INSERT INTO users (line_user_id) VALUES (?)", lineUserID)
	if err != nil {
		return 0, err
	}

	userID, err = result.LastInsertId()
	if err != nil {
		return 0, err
	}

	// Initialize stats and settings for new user
	_, _ = r.db.Exec("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", userID)
	_, _ = r.db.Exec("INSERT OR IGNORE INTO habit_settings (user_id) VALUES (?)", userID)

	return userID, nil
}

func (r *SQLiteRepository) GetAllUsers() ([]domain.User, error) {
	var users []domain.User
	err := r.db.Select(&users, "SELECT * FROM users")
	return users, err
}

func (r *SQLiteRepository) GetHabitRecord(userID int64, dateStr string) (*domain.HabitRecord, error) {
	var record domain.HabitRecord
	err := r.db.Get(&record, "SELECT * FROM habits WHERE date = ? AND user_id = ?", dateStr, userID)
	if err == nil {
		return &record, nil
	}

	if err != sql.ErrNoRows {
		return nil, err
	}

	// Create if not exists (upsert-like behavior)
	_, err = r.db.Exec("INSERT OR IGNORE INTO habits (date, user_id) VALUES (?, ?)", dateStr, userID)
	if err != nil {
		return nil, err
	}

	err = r.db.Get(&record, "SELECT * FROM habits WHERE date = ? AND user_id = ?", dateStr, userID)
	return &record, err
}

func (r *SQLiteRepository) RecordAction(userID int64, action string, timestamp string) (bool, error) {
	dateStr := time.Now().Format("2006-01-02")
	// Ensure record exists
	_, err := r.GetHabitRecord(userID, dateStr)
	if err != nil {
		return false, err
	}

	var query string
	if action == "wake" {
		query = "UPDATE habits SET wake_time = ? WHERE date = ? AND user_id = ? AND wake_time IS NULL"
	} else if action == "bath" {
		query = "UPDATE habits SET bath_time = ? WHERE date = ? AND user_id = ? AND bath_time IS NULL"
	} else {
		return false, fmt.Errorf("invalid action: %s", action)
	}

	res, err := r.db.Exec(query, timestamp, dateStr, userID)
	if err != nil {
		return false, err
	}

	rows, err := res.RowsAffected()
	return rows > 0, err
}

func (r *SQLiteRepository) GetStats(userID int64) (*domain.UserStats, error) {
	var stats domain.UserStats
	err := r.db.Get(&stats, "SELECT * FROM user_stats WHERE user_id = ?", userID)
	if err == sql.ErrNoRows {
		return &domain.UserStats{UserID: userID}, nil
	}
	return &stats, err
}

func (r *SQLiteRepository) UpdateConsecutiveFailures(userID int64, action string, failed bool) error {
	var query string
	if action == "wake" {
		if failed {
			query = "UPDATE user_stats SET wake_consecutive_failures = wake_consecutive_failures + 1 WHERE user_id = ?"
		} else {
			query = "UPDATE user_stats SET wake_consecutive_failures = 0 WHERE user_id = ?"
		}
	} else if action == "bath" {
		if failed {
			query = "UPDATE user_stats SET bath_consecutive_failures = bath_consecutive_failures + 1 WHERE user_id = ?"
		} else {
			query = "UPDATE user_stats SET bath_consecutive_failures = 0 WHERE user_id = ?"
		}
	}
	_, err := r.db.Exec(query, userID)
	return err
}

func (r *SQLiteRepository) GetHabitSettings(userID int64) (*domain.HabitSettings, error) {
	var settings domain.HabitSettings
	err := r.db.Get(&settings, "SELECT * FROM habit_settings WHERE user_id = ?", userID)
	if err == sql.ErrNoRows {
		// Return default
		return &domain.HabitSettings{UserID: userID, WakeDeadline: 540, BathDeadline: 1380}, nil
	}
	return &settings, err
}

func (r *SQLiteRepository) MarkTweeted(userID int64, action string, dateStr string) error {
	var query string
	if action == "wake" {
		query = "UPDATE habits SET wake_failed_tweeted = 1 WHERE date = ? AND user_id = ?"
	} else if action == "bath" {
		query = "UPDATE habits SET bath_failed_tweeted = 1 WHERE date = ? AND user_id = ?"
	}
	_, err := r.db.Exec(query, dateStr, userID)
	return err
}
