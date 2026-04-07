package line

import (
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

func (s *LineBotService) SendPushMessage(to, message string) error {
	if s.client == nil {
		fmt.Printf("--- [LINE Dry Run] ---\nTo: %s\nMessage: %s\n----------------------\n", to, message)
		return nil
	}

	_, err := s.client.PushMessage(&messaging_api.PushMessageRequest{
		To: to,
		Messages: []messaging_api.MessageInterface{
			&messaging_api.TextMessage{
				Text: message,
			},
		},
	}, "") // Second argument is x-line-retry-key
	return err
}

func (s *LineBotService) ReplyMessage(replyToken, message string) error {
	if s.client == nil {
		fmt.Printf("--- [LINE Dry Run Reply] ---\nToken: %s\nMessage: %s\n----------------------------\n", replyToken, message)
		return nil
	}

	_, err := s.client.ReplyMessage(&messaging_api.ReplyMessageRequest{
		ReplyToken: replyToken,
		Messages: []messaging_api.MessageInterface{
			&messaging_api.TextMessage{
				Text: message,
			},
		},
	})
	return err
}
