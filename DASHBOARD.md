# FDA Device Query Assistant Dashboard

A professional web interface for interacting with the FDA Device Query Agent.

## 🚀 Quick Start

```bash
# Run the dashboard
./run_dashboard.sh

# Or manually:
source .venv/bin/activate
python -m dashboard.app
```

Then open your browser to: **http://localhost:8000**

## 📊 Features

### Professional Interface
- **FDA-compliant design** with official blue/white color scheme
- **Real-time chat interface** with WebSocket support
- **Query templates** for common searches
- **Recent history** tracking
- **Export capabilities** (JSON, CSV)

### Smart Query Processing
- Natural language understanding
- Automatic endpoint routing
- Parameter extraction
- Result formatting

### Data Sources
- Device Recalls (Class I, II, III)
- 510(k) Clearances
- PMA Approvals
- Adverse Events (MAUDE)
- Device Classifications
- UDI Database
- Registration & Listing

## 💬 Example Queries

### Recalls
- "Show me Class I recalls from Abbott"
- "Find cardiac device recalls from 2024"
- "How many Class II recalls this year?"

### 510(k) Clearances
- "Show me K240190"
- "Find 510k clearances from Medtronic"
- "Recent orthopedic device clearances"

### Adverse Events
- "Show adverse events for pacemakers"
- "Find serious injuries from insulin pumps"
- "Recent events with patient deaths"

### Counts & Analytics
- "How many Class III devices?"
- "Count of recalls by classification"
- "Total PMAs approved in 2024"

## ⌨️ Keyboard Shortcuts

- `Ctrl + Enter` - Submit query
- `Ctrl + K` - Focus search box
- `Esc` - Clear input
- `Ctrl + /` - Show help

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=your_key_here
OPENFDA_API_KEY=your_key_here  # Optional, for higher rate limits
```

### Server Options
Edit `dashboard/app.py` to change:
- Port (default: 8000)
- Host (default: 0.0.0.0)
- CORS settings
- Session limits

## 📁 Dashboard Structure

```
dashboard/
├── app.py              # FastAPI backend server
├── static/
│   ├── index.html      # Main dashboard page
│   ├── css/
│   │   └── style.css   # Professional FDA styling
│   └── js/
│       ├── chat.js     # Chat interface logic
│       ├── results.js  # Results formatting
│       └── utils.js    # Utility functions
└── templates/          # Export templates
```

## 🎨 Design Principles

### FDA Compliance
- Professional government-appropriate design
- Accessibility features (WCAG 2.1 AA)
- Clear data attribution
- Proper disclaimers

### User Experience
- Clean, intuitive interface
- Real-time feedback
- Error handling
- Responsive design

### Data Presentation
- Formatted results with key information highlighted
- Classification badges (Class I/II/III)
- Sortable/filterable tables
- Export options for reporting

## 🔒 Security Notes

- Input sanitization to prevent XSS
- Session management
- Rate limiting ready
- CORS configuration

## 📈 API Endpoints

- `GET /` - Main dashboard
- `POST /query` - Submit query
- `GET /history` - Query history
- `GET /templates` - Query templates
- `GET /export/{format}` - Export results
- `WS /ws` - WebSocket for real-time chat
- `GET /health` - Health check
- `GET /docs` - API documentation

## 🐛 Troubleshooting

### Server won't start
- Check Python version (3.9+)
- Verify all dependencies: `pip install -r requirements.txt`
- Check port 8000 is available

### No results returned
- Verify ANTHROPIC_API_KEY is set
- Check internet connection
- Review agent logs

### WebSocket disconnects
- Check firewall settings
- Verify WebSocket support in browser
- Try refreshing the page

## 📝 Notes for FDA Analysts

This dashboard provides:
- **Instant access** to all FDA device databases
- **Natural language** queries - no need to learn API syntax
- **Formatted results** ready for reports
- **Audit trail** of all queries
- **Export options** for presentations

Perfect for:
- Preparing regulatory reports
- Investigating device issues
- Monitoring recall trends
- Analyzing adverse events
- Supporting decision-making

## 🚦 Status Indicators

- 🟢 **API Connected** - System ready
- 🔴 **Disconnected** - Check connection
- ⏳ **Processing** - Query in progress
- ✅ **Complete** - Results ready

## 📞 Support

For issues or questions about:
- **Dashboard**: Check this documentation
- **FDA Data**: Refer to openFDA.gov
- **Agent Logic**: See main project documentation