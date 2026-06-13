from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round12CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_realtime_and_queue_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "express": "^4.18.0",
    "ws": "^8.0.0",
    "eventsource": "^2.0.0",
    "kafkajs": "^2.0.0",
    "amqplib": "^0.10.0",
    "bullmq": "^5.0.0",
    "redis": "^4.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "server.js").write_text(
                """
const express = require('express');
const { WebSocketServer } = require('ws');
const { Kafka } = require('kafkajs');
const amqp = require('amqplib');
const { Queue, Worker } = require('bullmq');
const redis = require('redis');
const Particle = require('particle-api-js');

const app = express();
app.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.write('data: hello\\n\\n');
});
app.get('/feed-events', cors(), events.subscribe);

const wss = new WebSocketServer({ server, path: '/ws' });
wss.on('connection', (ws) => {
  ws.on('message', (message) => {});
});

const kafka = new Kafka({ clientId: 'specforge', brokers: ['localhost:9092'] });
const producer = kafka.producer();
const consumer = kafka.consumer({ groupId: 'orders' });
producer.send({ topic: 'orders.created', messages: [{ value: '1' }] });
consumer.subscribe({ topic: 'orders.created' });

async function queues() {
  const connection = await amqp.connect('amqp://localhost');
  const channel = await connection.createChannel();
  await channel.assertQueue('emails');
  channel.sendToQueue('emails', Buffer.from('hello'));
  channel.consume('emails', (message) => {});
}

const emailQueue = new Queue('email-jobs');
emailQueue.add('send-email', {});
new Worker('email-jobs', async (job) => {});

const publisher = redis.createClient();
const subscriber = redis.createClient();
publisher.publish('chat', 'hello');
subscriber.subscribe('chat', () => {});

const particle = new Particle();
const particleEventName = 'device.changed';
particle.getEventStream({ name: particleEventName, auth: 'token' });
particle.publishEvent({ name: 'device.command', data: '{}', auth: 'token' });
""".strip()
                + "\n",
                encoding="utf-8",
            )
            public = root / "public"
            public.mkdir()
            (public / "index.html").write_text(
                """
<!doctype html>
<script>
  const events = new EventSource('/events');
  const socket = new WebSocket('ws://localhost:3000/ws');
  socket.send('hello');
</script>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            for framework in {"websocket", "sse", "kafka", "rabbitmq", "bullmq", "redis-pubsub"}:
                self.assertIn(framework, frameworks)

            api_routes = {(route.framework, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("sse", "STREAM", "/events"), api_routes)
            self.assertIn(("sse", "STREAM", "/feed-events"), api_routes)
            self.assertIn(("websocket", "WS", "/ws"), api_routes)
            self.assertIn(("websocket", "EVENT", "websocket#connection"), api_routes)
            self.assertIn(("websocket", "EVENT", "websocket#message"), api_routes)
            self.assertIn(("kafka", "PRODUCE", "kafka#orders.created"), api_routes)
            self.assertIn(("kafka", "CONSUME", "kafka#orders.created"), api_routes)
            self.assertIn(("rabbitmq", "PRODUCE", "rabbitmq#emails"), api_routes)
            self.assertIn(("rabbitmq", "CONSUME", "rabbitmq#emails"), api_routes)
            self.assertIn(("bullmq", "PRODUCE", "bullmq#email-jobs"), api_routes)
            self.assertIn(("bullmq", "CONSUME", "bullmq#email-jobs"), api_routes)
            self.assertIn(("redis-pubsub", "PRODUCE", "redis#chat"), api_routes)
            self.assertIn(("redis-pubsub", "CONSUME", "redis#chat"), api_routes)
            self.assertIn(("sse", "CONSUME", "sse#device.changed"), api_routes)
            self.assertIn(("sse", "PRODUCE", "sse#device.command"), api_routes)

            api_calls = {(call.client, call.method, call.endpoint) for call in facts.api_calls}
            self.assertIn(("EventSource", "STREAM", "/events"), api_calls)
            self.assertIn(("WebSocket", "WS", "/ws"), api_calls)
            self.assertIn(("WebSocket", "EVENT", "websocket#message"), api_calls)

            api_links = {(link.method, link.endpoint, link.matched_route, link.confidence) for link in facts.api_links}
            self.assertIn(("STREAM", "/events", "/events", "high"), api_links)
            self.assertIn(("WS", "/ws", "/ws", "high"), api_links)
            self.assertIn(("EVENT", "websocket#message", "websocket#message", "high"), api_links)


if __name__ == "__main__":
    unittest.main()
