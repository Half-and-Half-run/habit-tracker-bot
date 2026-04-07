package domain

import "time"

// User represents a person using the habit tracker.
type User struct {
	ID         int64     `db:"id" json:"id"`
	LineUserID string    `db:"line_user_id" json:"line_user_id"`
	CreatedAt  time.Time `db:"created_at" json:"created_at"`
}

// HabitRecord represents a daily check-in for a specific habit.
type HabitRecord struct {
	Date                string  `db:"date" json:"date"`
	UserID              int64   `db:"user_id" json:"user_id"`
	WakeTime            *string `db:"wake_time" json:"wake_time"`
	BathTime            *string `db:"bath_time" json:"bath_time"`
	WakeFailedTweeted   int     `db:"wake_failed_tweeted" json:"wake_failed_tweeted"`
	BathFailedTweeted   int     `db:"bath_failed_tweeted" json:"bath_failed_tweeted"`
}

// UserStats tracks consecutive failures for habits.
type UserStats struct {
	UserID                   int64 `db:"user_id" json:"user_id"`
	WakeConsecutiveFailures  int   `db:"wake_consecutive_failures" json:"wake_consecutive_failures"`
	BathConsecutiveFailures  int   `db:"bath_consecutive_failures" json:"bath_consecutive_failures"`
}

// HabitSettings allows per-user customization of check-in times.
type HabitSettings struct {
	UserID       int64 `db:"user_id" json:"user_id"`
	WakeDeadline int   `db:"wake_deadline" json:"wake_deadline"` // Minutes since midnight
	BathDeadline int   `db:"bath_deadline" json:"bath_deadline"` // Minutes since midnight
}
