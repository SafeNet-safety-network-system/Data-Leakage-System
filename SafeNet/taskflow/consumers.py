from channels.generic.websocket import AsyncWebsocketConsumer
import json

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("alerts", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("alerts", self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message', '')

        # Here you could send the alert message to a group
        await self.channel_layer.group_send(
            "alerts",
            {
                'type': 'alert_message',
                'message': message
            }
        )

# consumers.py
    class NotificationConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            self.user_id = self.scope['user'].id
            self.group_name = f"user_{self.user_id}"

            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

        async def disconnect(self, close_code):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        async def send_notification(self, event):
            message = event['message']
            await self.send(text_data=message)

    async def alert_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'message': message
        }))


