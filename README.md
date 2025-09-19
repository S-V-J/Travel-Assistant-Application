# Open-Source Hybrid Multilingual Travel Assistant Application

## Overview

A production-ready web-based travel assistant combining **voice & chat interfaces** with advanced multilingual AI. Built on Rasa for dialogue management, hybrid MuRIL+IndicBERT models for English/Hindi/Hinglish support, FastAPI for async operations, Next.js PWA frontend, and Vocode for real-time voice interaction. Features comprehensive travel APIs (weather, flights, attractions, currency, time) with automated model training from user interactions.

**Project Status**: Foundation phases (Environment, LLM, Rasa Integration) completed September 18, 2025. Currently evolving through 10-phase development process to add multilingual voice capabilities, modern web interface, and production-scale deployment.

## 🎯 Evolution Roadmap

### ✅ **Completed Foundation (Phases 1-3)**
- **Core Backend**: Rasa framework with custom actions for travel APIs
- **LLM Integration**: Llama 3.2 (1B/3B) via llama-cpp-python with CPU fallback
- **Database**: SQLite with automated query logging and model training
- **Services**: Production systemd services with health monitoring
- **API Integration**: OpenWeatherMap, Amadeus, Geoapify, TimeZoneDB, currency conversion
- **Testing**: End-to-end validation with curl tests and service monitoring

### 🚀 **Active Development (Phases 4-10)**
- **Phase 4** (Current): Multilingual LLM upgrade to MuRIL+IndicBERT ensemble
- **Phase 5**: FastAPI migration with WebSocket support
- **Phase 6**: Vocode voice integration with Whisper STT + Piper TTS
- **Phase 7**: Next.js PWA frontend with real-time voice/chat UI
- **Phase 8**: Streamlit admin dashboard with training management
- **Phase 9**: Docker + AWS production deployment
- **Phase 10**: Comprehensive testing and optimization

## Tagline for Donation

**"Building the future of multilingual AI travel assistance – your support powers innovation!"**

## Usage & Collaboration

This repository is **public** for learning, research, and building derivative works. The codebase is available under MIT license for cloning, forking, and adaptation. **Direct modification access** is restricted to invited collaborators.

### Contact & Support
- **Email**: [stjl093@gmail.com](mailto:stjl093@gmail.com)
- **Phone**: +918095875948
- **LinkedIn**: [linkedin.com/in/sid-093](https://linkedin.com/in/sid-093)
- **Donate**: [PayPal Donation Link](https://www.paypal.com/ncp/payment/2J5NTJBYW2HL8)

For collaboration, contract work, feature requests, or technical support, reach out via any channel above.

## 🌟 Features

### **Current Capabilities**
- **Conversational AI**: Context-aware dialogue with proactive suggestions
- **Travel Services**: Weather forecasting, flight search, attraction recommendations, currency conversion, time zone queries
- **Smart Training**: Automated Rasa model updates every 6 hours from real user interactions
- **Production Services**: Systemd-managed microservices with health monitoring
- **API Integration**: RESTful endpoints tested via curl with validated responses

### **Planned Enhancements**
- **Multilingual Support**: Fluent English, Hindi, and Hinglish (code-mixed) conversations
- **Voice Interaction**: Real-time speech-to-text and text-to-speech with <500ms latency
- **Modern Web UI**: Next.js PWA with responsive design and offline capabilities
- **Advanced Analytics**: Comprehensive conversation tracking and model performance metrics
- **Scalable Deployment**: Docker containerization with AWS auto-scaling

## 🏗️ Architecture

### **Current Stack**
- **Backend**: Flask + Rasa 3.6+ + Custom Actions + API Integrations
- **LLM**: Llama 3.2 (1B/3B) via llama-cpp-python with CPU optimization
- **Database**: SQLite with query_history.db and exchange_rates.db
- **Services**: Systemd (rasa.service, rasa_actions.service, currency_converter.service, rasa_train.service)
- **APIs**: OpenWeatherMap, Amadeus, Geoapify, TimeZoneDB, ExchangeRate-API

### **Target Architecture**
- **Backend**: FastAPI + Rasa + Vocode + WebSocket support
- **LLM**: MuRIL+IndicBERT ensemble via vLLM with 4-bit quantization
- **Database**: PostgreSQL with advanced conversation analytics
- **Frontend**: Next.js PWA with real-time voice/chat interface
- **Voice**: Whisper.cpp (STT) + Piper TTS with multilingual models
- **Deployment**: Docker Compose + AWS ECS/Fargate

## 🚀 Setup Instructions

### **Current Setup (Foundation)**
```bash
# Clone and setup
git clone https://github.com/S-V-J/Travel-Assistant-Application.git
cd Travel-Assistant-Application/livekit-travel-assistant

# Virtual environments
source llm_venv/bin/activate  # For LLM operations
# OR
source rasa-bot/rasa_venv/bin/activate  # For Rasa operations

# Dependencies
pip install -r requirements.txt

# Database initialization
python3 db/init_db.py

# Service deployment
sudo cp systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rasa.service rasa_actions.service rasa_train.service currency_converter.service

# Training and testing
cd rasa-bot && rasa train
curl -X POST http://localhost:5005/webhooks/rest/webhook -d '{"sender": "test", "message": "weather in Paris"}'
```

### **Future Setup (After Migration)**
```bash
# Full stack deployment
docker-compose up -d
# Access: http://localhost:3000 (main app), http://localhost:8501 (admin)

# AWS deployment
terraform apply aws/infrastructure.tf
```

## 🧪 Testing & Validation

### **Current Tests (Verified)**
- **Weather Queries**: `curl` → "Current weather in Paris: 25.38°C, clear sky. Pack light clothes and sunglasses!"
- **Flight Searches**: `curl` → "Just to confirm, you want a flight from New York to London?"
- **Currency Conversion**: `curl` → "100.0 USD is 85.21 EUR—that's about the cost of a nice dinner!"
- **Service Health**: All systemd services active and responsive
- **Database Logging**: Query history tracked with automatic de-duplication

### **Planned Testing**
- **Multilingual**: Hindi/Hinglish conversation validation
- **Voice Pipeline**: End-to-end STT→NLU→TTS testing
- **Load Testing**: 1,000 concurrent users via Locust
- **Integration**: Full conversation flows with voice interruption handling

## 🔧 Known Issues & Solutions

- **✅ Fixed: SQLAlchemy Warning** → Suppressed via environment variables in service configs
- **✅ Fixed: Piper TTS Path** → Resolved with proper directory structure
- **✅ Fixed: Entity Extraction** → Enhanced NLU patterns for partial flight information
- **✅ Fixed: Training Conflicts** → Refined rules.yml for consistent behavior
- **✅ Fixed: Database Schema** → Added query_count column with backward compatibility
- **⚠️ In Progress: LLM Fallback** → Migrating to MuRIL+IndicBERT for better unknown query handling

## 📈 Development Status

| Component | Foundation | Migration | Status |
|-----------|------------|-----------|---------|
| Rasa Core | ✅ Complete | 🔄 FastAPI Integration | Active |
| LLM Engine | ✅ Llama 3.2 | 🔄 MuRIL+IndicBERT | Phase 4 |
| Database | ✅ SQLite | 🔄 PostgreSQL | Planned |
| Voice Layer | ❌ Not Started | 🔄 Vocode Integration | Phase 6 |
| Frontend | ❌ Not Started | 🔄 Next.js PWA | Phase 7 |
| Production | ✅ Systemd | 🔄 Docker+AWS | Phase 9 |

## 🎯 Project Goals

**Primary Objective**: Build a production-ready multilingual travel assistant that seamlessly handles voice and text interactions in English, Hindi, and Hinglish.

**Secondary Objectives**:
- Demonstrate modern AI architecture patterns
- Showcase open-source tool integration
- Provide educational reference implementation
- Enable community-driven enhancements

**Success Metrics**:
- <500ms voice response latency
- 95%+ intent recognition accuracy
- Support for 1,000+ concurrent users
- Natural code-switching in conversations

---

**License**: MIT | **Last Updated**: September 19, 2025 | **Version**: 2.0 (Migration Phase)