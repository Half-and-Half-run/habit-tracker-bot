package main

import (
	"log"
	"os"

	"habit-tracker-bot/internal/delivery/http"
	"habit-tracker-bot/internal/infrastructure/db"
	"habit-tracker-bot/internal/infrastructure/line"
	"habit-tracker-bot/internal/usecase"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/robfig/cron/v3"
)

func main() {
	// Load .env for local development
	_ = godotenv.Load()

	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "data/habits.db"
	}

	// Initialize infrastructure
	repo, err := db.NewSQLiteRepository(dbPath)
	if err != nil {
		log.Fatalf("Failed to initialize db: %v", err)
	}

	if err := repo.InitSchema(); err != nil {
		log.Fatalf("Failed to initialize schema: %v", err)
	}

	lineBot, err := line.NewLineBotService()
	if err != nil {
		log.Fatalf("Failed to initialize LINE bot: %v", err)
	}

	// Initialize usecase
	habitUsecase := usecase.NewHabitUsecase(repo, lineBot)

	// Initialize scheduler (check every 5 minutes)
	c := cron.New()
	_, err = c.AddFunc("*/5 * * * *", func() {
		log.Println("[Cron] Checking habit deadlines...")
		habitUsecase.ProcessDeadlines()
	})
	if err != nil {
		log.Fatalf("Failed to add cron job: %v", err)
	}
	c.Start()
	log.Println("Background scheduler started.")

	// Initialize HTTP delivery
	handler := http.NewHabitHandler(habitUsecase)

	r := gin.Default()

	r.POST("/callback", handler.LineCallback)
	r.POST("/checkin", handler.Checkin)
	r.GET("/status/:user_id", handler.GetStatus)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}

	log.Printf("Starting server on port %s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("Failed to run server: %v", err)
	}
}
