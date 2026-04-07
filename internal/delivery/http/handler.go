package http

import (
	"fmt"
	"net/http"
	"strconv"

	"habit-tracker-bot/internal/usecase"
	"github.com/gin-gonic/gin"
)

type HabitHandler struct {
	usecase *usecase.HabitUsecase
}

func NewHabitHandler(u *usecase.HabitUsecase) *HabitHandler {
	return &HabitHandler{usecase: u}
}

type CheckinRequest struct {
	UserID    int64  `json:"user_id" binding:"required"`
	Action    string `json:"action" binding:"required"`
	Timestamp string `json:"timestamp"`
}

func (h *HabitHandler) Checkin(c *gin.Context) {
	var req CheckinRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Action != "wake" && req.Action != "bath" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid action"})
		return
	}

	status, err := h.usecase.Checkin(req.UserID, req.Action)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": status, "message": fmt.Sprintf("%s recorded.", req.Action)})
}

func (h *HabitHandler) GetStatus(c *gin.Context) {
	idParam := c.Param("user_id")
	userID, err := strconv.ParseInt(idParam, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user_id"})
		return
	}

	status, err := h.usecase.GetStatus(userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, status)
}

func (h *HabitHandler) LineCallback(c *gin.Context) {
	// Simple callback for now
	// In a real app, you would use line-bot-sdk-go/webhook to verify signatures
	var body map[string]interface{}
	if err := c.BindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	events, ok := body["events"].([]interface{})
	if !ok {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
		return
	}

	for _, e := range events {
		event := e.(map[string]interface{})
		source, _ := event["source"].(map[string]interface{})
		lineUserID, _ := source["userId"].(string)

		if lineUserID != "" {
			userID, _ := h.usecase.RegisterUser(lineUserID)
			fmt.Printf("User registered/detected: %d (LINE: %s)\n", userID, lineUserID[:8])
		}
	}

	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}
