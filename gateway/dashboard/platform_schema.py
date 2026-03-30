"""
Data-driven platform configuration schema.

Maps each gateway.config.Platform enum value to its form field definitions,
display metadata, and test-connection support flag. A single Jinja2 template
iterates this schema to render platform-specific configuration forms.

Adding a new platform adapter requires only a new entry in PLATFORM_SCHEMA.
"""

from gateway.config import Platform


PLATFORM_SCHEMA = {
    Platform.LOCAL: {
        "display_name": "Local CLI",
        "fields": [],
        "test_supported": False,
        "configurable": False,
    },

    Platform.TELEGRAM: {
        "display_name": "Telegram",
        "fields": [
            {
                "name": "TELEGRAM_BOT_TOKEN",
                "label": "Bot Token",
                "type": "password",
                "required": True,
                "help": "Telegram bot token from @BotFather",
                "help_url": "https://t.me/BotFather",
            },
            {
                "name": "TELEGRAM_ALLOWED_USERS",
                "label": "Allowed Users",
                "type": "text",
                "required": False,
                "help": "Comma-separated Telegram user IDs allowed to use the bot",
                "help_url": "https://t.me/userinfobot",
            },
            {
                "name": "TELEGRAM_HOME_CHANNEL",
                "label": "Home Channel",
                "type": "text",
                "required": False,
                "help": "Default channel ID for proactive messages (cron, notifications)",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.DISCORD: {
        "display_name": "Discord",
        "fields": [
            {
                "name": "DISCORD_BOT_TOKEN",
                "label": "Bot Token",
                "type": "password",
                "required": True,
                "help": "Discord bot token from Developer Portal",
                "help_url": "https://discord.com/developers/applications",
            },
            {
                "name": "DISCORD_ALLOWED_USERS",
                "label": "Allowed Users",
                "type": "text",
                "required": False,
                "help": "Comma-separated Discord user IDs allowed to use the bot",
                "help_url": None,
            },
            {
                "name": "DISCORD_HOME_CHANNEL",
                "label": "Home Channel",
                "type": "text",
                "required": False,
                "help": "Default channel ID for proactive messages (cron, notifications)",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.SLACK: {
        "display_name": "Slack",
        "fields": [
            {
                "name": "SLACK_BOT_TOKEN",
                "label": "Bot Token",
                "type": "password",
                "required": True,
                "help": "Slack bot token (xoxb-). Required scopes: chat:write, app_mentions:read, channels:history, groups:history, im:history, im:read, im:write, users:read, files:write",
                "help_url": "https://api.slack.com/apps",
            },
            {
                "name": "SLACK_APP_TOKEN",
                "label": "App Token",
                "type": "password",
                "required": True,
                "help": "Slack app-level token (xapp-) for Socket Mode. Enable Event Subscriptions: message.im, message.channels, message.groups, app_mention",
                "help_url": "https://api.slack.com/apps",
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.MATTERMOST: {
        "display_name": "Mattermost",
        "fields": [
            {
                "name": "MATTERMOST_URL",
                "label": "Server URL",
                "type": "text",
                "required": True,
                "help": "Mattermost server URL (e.g. https://mm.example.com)",
                "help_url": "https://mattermost.com/deploy/",
            },
            {
                "name": "MATTERMOST_TOKEN",
                "label": "Bot Token",
                "type": "password",
                "required": True,
                "help": "Mattermost bot token or personal access token",
                "help_url": None,
            },
            {
                "name": "MATTERMOST_ALLOWED_USERS",
                "label": "Allowed Users",
                "type": "text",
                "required": False,
                "help": "Comma-separated Mattermost user IDs allowed to use the bot",
                "help_url": None,
            },
            {
                "name": "MATTERMOST_REQUIRE_MENTION",
                "label": "Require @mention",
                "type": "text",
                "required": False,
                "help": "Require @mention in channels (default: true). Set to false to respond to all messages.",
                "help_url": None,
            },
            {
                "name": "MATTERMOST_FREE_RESPONSE_CHANNELS",
                "label": "Free Response Channels",
                "type": "text",
                "required": False,
                "help": "Comma-separated channel IDs where bot responds without @mention",
                "help_url": None,
            },
            {
                "name": "MATTERMOST_HOME_CHANNEL",
                "label": "Home Channel",
                "type": "text",
                "required": False,
                "help": "Default channel for proactive messages (cron, notifications)",
                "help_url": None,
            },
            {
                "name": "MATTERMOST_REPLY_MODE",
                "label": "Reply Mode",
                "type": "text",
                "required": False,
                "help": "How the bot replies in channels (thread or channel)",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.MATRIX: {
        "display_name": "Matrix",
        "fields": [
            {
                "name": "MATRIX_HOMESERVER",
                "label": "Homeserver URL",
                "type": "text",
                "required": True,
                "help": "Matrix homeserver URL (e.g. https://matrix.example.org)",
                "help_url": "https://matrix.org/ecosystem/servers/",
            },
            {
                "name": "MATRIX_USER_ID",
                "label": "User ID",
                "type": "text",
                "required": True,
                "help": "Matrix user ID (e.g. @hermes:example.org)",
                "help_url": None,
            },
            {
                "name": "MATRIX_ACCESS_TOKEN",
                "label": "Access Token",
                "type": "password",
                "required": False,
                "help": "Matrix access token (preferred over password login)",
                "help_url": None,
            },
            {
                "name": "MATRIX_PASSWORD",
                "label": "Password",
                "type": "password",
                "required": False,
                "help": "Matrix password (used if access token is not set)",
                "help_url": None,
            },
            {
                "name": "MATRIX_ALLOWED_USERS",
                "label": "Allowed Users",
                "type": "text",
                "required": False,
                "help": "Comma-separated Matrix user IDs allowed to use the bot (@user:server format)",
                "help_url": None,
            },
            {
                "name": "MATRIX_ENCRYPTION",
                "label": "Encryption",
                "type": "text",
                "required": False,
                "help": "Enable end-to-end encryption (true/false)",
                "help_url": None,
            },
            {
                "name": "MATRIX_HOME_ROOM",
                "label": "Home Room",
                "type": "text",
                "required": False,
                "help": "Default room for proactive messages (cron, notifications)",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.SIGNAL: {
        "display_name": "Signal",
        "fields": [
            {
                "name": "SIGNAL_ACCOUNT",
                "label": "Account",
                "type": "text",
                "required": True,
                "help": "Signal phone number or UUID for the bot account",
                "help_url": None,
            },
            {
                "name": "SIGNAL_HTTP_URL",
                "label": "Signal CLI HTTP URL",
                "type": "text",
                "required": True,
                "help": "URL of the signal-cli-rest-api HTTP endpoint",
                "help_url": None,
            },
            {
                "name": "SIGNAL_ALLOWED_USERS",
                "label": "Allowed Users",
                "type": "text",
                "required": False,
                "help": "Comma-separated Signal phone numbers or UUIDs allowed to use the bot",
                "help_url": None,
            },
            {
                "name": "SIGNAL_GROUP_ALLOWED_USERS",
                "label": "Group Allowed Users",
                "type": "text",
                "required": False,
                "help": "Comma-separated Signal identifiers allowed in group chats",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.HOMEASSISTANT: {
        "display_name": "Home Assistant",
        "fields": [
            {
                "name": "HASS_TOKEN",
                "label": "Access Token",
                "type": "password",
                "required": True,
                "help": "Home Assistant long-lived access token",
                "help_url": None,
            },
            {
                "name": "HASS_URL",
                "label": "Server URL",
                "type": "text",
                "required": False,
                "help": "Home Assistant URL (default: http://homeassistant.local:8123)",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.EMAIL: {
        "display_name": "Email",
        "fields": [
            {
                "name": "EMAIL_ADDRESS",
                "label": "Email Address",
                "type": "text",
                "required": True,
                "help": "Email address for sending and receiving",
                "help_url": None,
            },
            {
                "name": "EMAIL_PASSWORD",
                "label": "Password",
                "type": "password",
                "required": True,
                "help": "Email account password or app-specific password",
                "help_url": None,
            },
            {
                "name": "EMAIL_IMAP_HOST",
                "label": "IMAP Host",
                "type": "text",
                "required": True,
                "help": "IMAP server hostname for receiving email",
                "help_url": None,
            },
            {
                "name": "EMAIL_IMAP_PORT",
                "label": "IMAP Port",
                "type": "text",
                "required": False,
                "help": "IMAP server port (default: 993)",
                "help_url": None,
            },
            {
                "name": "EMAIL_SMTP_HOST",
                "label": "SMTP Host",
                "type": "text",
                "required": True,
                "help": "SMTP server hostname for sending email",
                "help_url": None,
            },
            {
                "name": "EMAIL_SMTP_PORT",
                "label": "SMTP Port",
                "type": "text",
                "required": False,
                "help": "SMTP server port (default: 587)",
                "help_url": None,
            },
            {
                "name": "EMAIL_POLL_INTERVAL",
                "label": "Poll Interval",
                "type": "text",
                "required": False,
                "help": "Seconds between inbox checks (default: 15)",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.SMS: {
        "display_name": "SMS (Twilio)",
        "fields": [
            {
                "name": "TWILIO_ACCOUNT_SID",
                "label": "Account SID",
                "type": "text",
                "required": True,
                "help": "Twilio account SID",
                "help_url": None,
            },
            {
                "name": "TWILIO_AUTH_TOKEN",
                "label": "Auth Token",
                "type": "password",
                "required": True,
                "help": "Twilio authentication token",
                "help_url": None,
            },
            {
                "name": "TWILIO_PHONE_NUMBER",
                "label": "Phone Number",
                "type": "text",
                "required": True,
                "help": "Twilio phone number for sending SMS",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.DINGTALK: {
        "display_name": "DingTalk",
        "fields": [
            {
                "name": "DINGTALK_CLIENT_ID",
                "label": "Client ID",
                "type": "text",
                "required": True,
                "help": "DingTalk application client ID (AppKey)",
                "help_url": None,
            },
            {
                "name": "DINGTALK_CLIENT_SECRET",
                "label": "Client Secret",
                "type": "password",
                "required": True,
                "help": "DingTalk application client secret (AppSecret)",
                "help_url": None,
            },
        ],
        "test_supported": True,
        "configurable": True,
    },

    Platform.WHATSAPP: {
        "display_name": "WhatsApp",
        "fields": [
            {
                "name": "WHATSAPP_ENABLED",
                "label": "Enabled",
                "type": "text",
                "required": False,
                "help": "Enable WhatsApp adapter (true/false)",
                "help_url": None,
            },
            {
                "name": "WHATSAPP_MODE",
                "label": "Mode",
                "type": "text",
                "required": False,
                "help": "WhatsApp connection mode",
                "help_url": None,
            },
        ],
        "test_supported": False,
        "configurable": True,
    },

    Platform.API_SERVER: {
        "display_name": "API Server",
        "fields": [
            {
                "name": "API_SERVER_ENABLED",
                "label": "Enabled",
                "type": "text",
                "required": False,
                "help": "Enable the OpenAI-compatible API server (true/false)",
                "help_url": None,
            },
            {
                "name": "API_SERVER_KEY",
                "label": "API Key",
                "type": "password",
                "required": False,
                "help": "Bearer token for API server authentication. If empty, all requests are allowed.",
                "help_url": None,
            },
            {
                "name": "API_SERVER_PORT",
                "label": "Port",
                "type": "text",
                "required": False,
                "help": "Port for the API server (default: 8642)",
                "help_url": None,
            },
            {
                "name": "API_SERVER_HOST",
                "label": "Host",
                "type": "text",
                "required": False,
                "help": "Bind address for the API server (default: 127.0.0.1). Use 0.0.0.0 for network access.",
                "help_url": None,
            },
        ],
        "test_supported": False,
        "configurable": True,
    },

    Platform.WEBHOOK: {
        "display_name": "Webhook",
        "fields": [
            {
                "name": "WEBHOOK_ENABLED",
                "label": "Enabled",
                "type": "text",
                "required": False,
                "help": "Enable the webhook platform adapter (true/false)",
                "help_url": None,
            },
            {
                "name": "WEBHOOK_PORT",
                "label": "Port",
                "type": "text",
                "required": False,
                "help": "Port for the webhook HTTP server (default: 8644)",
                "help_url": None,
            },
            {
                "name": "WEBHOOK_SECRET",
                "label": "Secret",
                "type": "password",
                "required": False,
                "help": "Global HMAC secret for webhook signature validation",
                "help_url": None,
            },
        ],
        "test_supported": False,
        "configurable": True,
    },
}
