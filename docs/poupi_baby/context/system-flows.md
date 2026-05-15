# System Flows
→ Backend API
→ Redis Cache
→ PostgreSQL
→ Backend API
→ Frontend


## Price Collection Flow
Scheduler / Cron
→ Queue
→ Workers / Crawlers
→ Marketplaces
→ Data Normalization
→ PostgreSQL
→ Redis Cache


## Price Update Flow
Crawler detects change
→ Compare previous price
→ Save historical data
→ Trigger update event
→ Update cache
→ Validate active alerts


## Alert Flow
Price reaches target
→ System identifies subscribed users
→ Notification Service
→ Email / Push / Telegram


## Premium Flow
User subscribes
→ Payment Gateway
→ Backend validates subscription
→ Update permissions
→ Enable premium features


## AI Flow

System collects:
- price history
- trends
- user behavior
- monitored products

→ AI Engine processes data
→ Generate smart recommendations