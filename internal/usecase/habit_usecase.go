package usecase

import (
	"fmt"
	"time"

	"github.com/line/line-bot-sdk-go/v8/linebot/messaging_api"
	"habit-tracker-bot/internal/domain"
	"habit-tracker-bot/internal/infrastructure/db"
	"habit-tracker-bot/internal/infrastructure/line"
)

type HabitUsecase struct {
	repo    *db.SQLiteRepository
	lineBot *line.LineBotService
}

func NewHabitUsecase(repo *db.SQLiteRepository, lineBot *line.LineBotService) *HabitUsecase {
	return &HabitUsecase{
		repo:    repo,
		lineBot: lineBot,
	}
}

func (u *HabitUsecase) RegisterUser(lineUserID string) (int64, error) {
	return u.repo.GetOrRegisterUser(lineUserID)
}

func (u *HabitUsecase) Checkin(userID int64, action string) (string, error) {
	timestamp := time.Now().Format(time.RFC3339)
	updated, err := u.repo.RecordAction(userID, action, timestamp)
	if err != nil {
		return "", err
	}

	if !updated {
		return "ignored", nil
	}

	// Reset consecutive failures
	_ = u.repo.UpdateConsecutiveFailures(userID, action, false)

	// Send success notification via LINE
	// Actually, we need to get the lineUserID for the given userID
	users, _ := u.repo.GetAllUsers()
	var lineUserID string
	for _, u_ := range users {
		if u_.ID == userID {
			lineUserID = u_.LineUserID
			break
		}
	}

	if lineUserID != "" {
		msg := fmt.Sprintf("%s mission accomplished!\nGreat job!\nTime: %s", action, timestamp)
		_ = u.lineBot.SendMessage(lineUserID, []messaging_api.MessageInterface{
			&messaging_api.TextMessage{Text: msg},
		})
	}

	return "success", nil
}

func (u *HabitUsecase) GetStatus(userID int64) (map[string]interface{}, error) {
	dateStr := time.Now().Format("2006-01-02")
	record, err := u.repo.GetHabitRecord(userID, dateStr)
	if err != nil {
		return nil, err
	}

	stats, err := u.repo.GetStats(userID)
	if err != nil {
		return nil, err
	}

	return map[string]interface{}{
		"user_id":      userID,
		"today_record": record,
		"stats":        stats,
	}, nil
}

func (u *HabitUsecase) ProcessDeadlines() {
	now := time.Now()
	dateStr := now.Format("2006-01-02")
	currentMinutes := now.Hour()*60 + now.Minute()

	users, err := u.repo.GetAllUsers()
	if err != nil {
		return
	}

	for _, user := range users {
		settings, _ := u.repo.GetHabitSettings(user.ID)
		record, _ := u.repo.GetHabitRecord(user.ID, dateStr)

		// Wake check
		if currentMinutes >= settings.WakeDeadline {
			if record.WakeTime == nil && record.WakeFailedTweeted == 0 {
				_ = u.repo.UpdateConsecutiveFailures(user.ID, "wake", true)
				stats, _ := u.repo.GetStats(user.ID)
				msg := fmt.Sprintf("!!! Nido-ne Shitemasu !!!\n\n[Warning] Kishou mission failed.\nConsecutive failures: %d\nTime: %s",
					stats.WakeConsecutiveFailures, now.Format(time.RFC3339))
				_ = u.lineBot.SendMessage(user.LineUserID, []messaging_api.MessageInterface{
					&messaging_api.TextMessage{Text: msg},
				})
				_ = u.repo.MarkTweeted(user.ID, "wake", dateStr)
			}
		}

		// Bath check
		if currentMinutes >= settings.BathDeadline {
			if record.BathTime == nil && record.BathFailedTweeted == 0 {
				_ = u.repo.UpdateConsecutiveFailures(user.ID, "bath", true)
				stats, _ := u.repo.GetStats(user.ID)
				msg := fmt.Sprintf("!!! Ofuro Haitte naidesu !!!\n\n[Warning] Nyuuyoku mission failed.\nConsecutive failures: %d\nTime: %s",
					stats.BathConsecutiveFailures, now.Format(time.RFC3339))
				_ = u.lineBot.SendMessage(user.LineUserID, []messaging_api.MessageInterface{
					&messaging_api.TextMessage{Text: msg},
				})
				_ = u.repo.MarkTweeted(user.ID, "bath", dateStr)
			}
		}
	}
}

func (u *HabitUsecase) ReplyStatus(lineUserID, replyToken string) error {
	userID, err := u.repo.GetOrRegisterUser(lineUserID)
	if err != nil {
		return err
	}

	status, err := u.GetStatus(userID)
	if err != nil {
		return err
	}

	stats := status["stats"].(*domain.UserStats)
	record := status["today_record"].(*domain.HabitRecord)

	msg := fmt.Sprintf("Current Status for User %d:\n\n", userID)
	if record.WakeTime != nil {
		msg += fmt.Sprintf("Wake: Success (%s)\n", *record.WakeTime)
	} else {
		msg += "Wake: Not Yet\n"
	}

	if record.BathTime != nil {
		msg += fmt.Sprintf("Bath: Success (%s)\n", *record.BathTime)
	} else {
		msg += "Bath: Not Yet\n"
	}

	msg += fmt.Sprintf("\nConsecutive Failures:\nWake: %d\nBath: %d",
		stats.WakeConsecutiveFailures, stats.BathConsecutiveFailures)

	return u.lineBot.ReplyMessages(replyToken, []messaging_api.MessageInterface{
		&messaging_api.TextMessage{Text: msg},
	})
}
