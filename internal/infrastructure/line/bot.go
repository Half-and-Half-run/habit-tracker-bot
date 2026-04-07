package line

import (
	"context"
	"fmt"
	"os"

	"github.com/line/line-bot-sdk-go/v8/linebot/messaging_api"
)

type LineBotService struct {
	client *messaging_api.MessagingApiAPI
}

func NewLineBotService() (*LineBotService, error) {
	token := os.Getenv("LINE_CHANNEL_ACCESS_TOKEN")
	if token == "" {
		return &LineBotService{client: nil}, nil
	}

	client, err := messaging_api.NewMessagingApiAPI(token)
	if err != nil {
		return nil, err
	}

	return &LineBotService{client: client}, nil
}

func (s *LineBotService) SendMessage(to string, messages []messaging_api.MessageInterface) error {
	if s.client == nil {
		fmt.Printf("--- [LINE Dry Run] ---\nTo: %s\nMessages: %v\n----------------------\n", to, messages)
		return nil
	}

	_, err := s.client.PushMessage(&messaging_api.PushMessageRequest{
		To:       to,
		Messages: messages,
	}, "") // x-line-retry-key
	return err
}

func (s *LineBotService) ReplyMessages(replyToken string, messages []messaging_api.MessageInterface) error {
	if s.client == nil {
		fmt.Printf("--- [LINE Dry Run Reply] ---\nToken: %s\nMessages: %v\n----------------------------\n", replyToken, messages)
		return nil
	}

	_, err := s.client.ReplyMessage(&messaging_api.ReplyMessageRequest{
		ReplyToken: replyToken,
		Messages:   messages,
	})
	return err
}
