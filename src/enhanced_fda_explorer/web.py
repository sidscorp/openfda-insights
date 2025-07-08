"""
Enhanced Web Interface for FDA Explorer using Streamlit
"""

import asyncio
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from .core import FDAExplorer
from .config import get_config, load_config, validate_current_config
from .visualization import DataVisualizer


# Page configuration
st.set_page_config(
    page_title="Enhanced FDA Explorer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .reportview-container {
        background: linear-gradient(90deg, #f8f9fa 0%, #e9ecef 100%);
    }
    .main .block-container {
        padding-top: 2rem;
    }
    .stAlert {
        border-radius: 10px;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def get_config_cached():
    """Get configuration (cached)"""
    return get_config()


@st.cache_data(ttl=3600)
def search_fda_data_cached(query: str, query_type: str, endpoints: List[str], 
                          limit: int, include_ai_analysis: bool, date_range_months: int):
    """Cached FDA data search"""
    config = get_config_cached()
    
    # Create event loop if none exists
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    explorer = FDAExplorer(config)
    
    try:
        # Prepare date range
        date_range = None
        if date_range_months:
            date_range = {
                "start_date": datetime.now() - timedelta(days=date_range_months * 30),
                "end_date": datetime.now()
            }
        
        # Perform search
        response = loop.run_until_complete(
            explorer.search(
                query=query,
                query_type=query_type,
                endpoints=endpoints,
                limit=limit,
                include_ai_analysis=include_ai_analysis,
                date_range=date_range
            )
        )
        
        return response
    
    finally:
        explorer.close()


def main():
    """Main web interface"""
    
    # Header
    st.title("🔍 Enhanced FDA Explorer")
    st.markdown("### Next-generation FDA medical device data exploration platform")
    
    # Configuration validation check
    try:
        validation_summary = validate_current_config()
        
        # Show configuration warnings if any
        if validation_summary["errors"] or validation_summary["critical"]:
            st.error("⚠️ **Configuration Issues Detected**")
            
            all_issues = validation_summary["critical"] + validation_summary["errors"]
            for issue in all_issues:
                st.error(f"• {issue}")
            
            st.info("Please fix configuration issues for optimal performance. Some features may be unavailable.")
        
        elif validation_summary["warnings"]:
            with st.expander("⚠️ Configuration Warnings", expanded=False):
                for warning in validation_summary["warnings"]:
                    st.warning(f"• {warning}")
        
        elif validation_summary["info"]:
            with st.expander("ℹ️ Configuration Info", expanded=False):
                for info in validation_summary["info"]:
                    st.info(f"• {info}")
                    
    except Exception as e:
        st.error(f"Configuration validation failed: {e}")
    
    # Disclaimer
    st.error("""
    ⚠️ **UNOFFICIAL TOOL**: This is an independent research demo and is NOT affiliated with, 
    endorsed by, or representing the U.S. Food and Drug Administration. All data comes from the public openFDA API.
    """)
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Search settings
        st.subheader("Search Settings")
        query_type = st.selectbox(
            "Query Type",
            ["device", "manufacturer"],
            help="Search for devices or manufacturers"
        )
        
        endpoints = st.multiselect(
            "Data Sources",
            ["event", "recall", "510k", "pma", "classification", "udi"],
            default=["event", "recall", "510k", "pma", "classification", "udi"],
            help="Select which FDA databases to search"
        )
        
        limit = st.slider(
            "Results per Source",
            min_value=10,
            max_value=500,
            value=100,
            help="Maximum results per data source"
        )
        
        date_range_months = st.slider(
            "Date Range (months)",
            min_value=1,
            max_value=60,
            value=12,
            help="How far back to search"
        )
        
        # Analysis settings
        st.subheader("Analysis Settings")
        include_ai_analysis = st.checkbox(
            "Include AI Analysis",
            value=True,
            help="Include AI-powered insights and analysis"
        )
        
        show_visualizations = st.checkbox(
            "Show Visualizations",
            value=True,
            help="Display interactive charts and graphs"
        )
        
        show_raw_data = st.checkbox(
            "Show Raw Data",
            value=False,
            help="Display raw data tables"
        )
    
    # Main interface
    tab1, tab2, tab3, tab4 = st.tabs(["🔍 Search", "📊 Device Intelligence", "📈 Trends", "⚙️ Advanced"])
    
    with tab1:
        st.header("FDA Data Search")
        
        # Search input
        query = st.text_input(
            "Search Query",
            placeholder="e.g., pacemaker, Medtronic, insulin pump",
            help="Enter device name or manufacturer"
        )
        
        if st.button("Search", type="primary") and query:
            with st.spinner("Searching FDA databases..."):
                try:
                    response = search_fda_data_cached(
                        query=query,
                        query_type=query_type,
                        endpoints=endpoints,
                        limit=limit,
                        include_ai_analysis=include_ai_analysis,
                        date_range_months=date_range_months
                    )
                    
                    # Display results
                    _display_search_results(response, show_visualizations, show_raw_data)
                    
                except Exception as e:
                    st.error(f"Search failed: {str(e)}")
    
    with tab2:
        st.header("Device Intelligence")
        
        device_name = st.text_input(
            "Device Name",
            placeholder="e.g., pacemaker, insulin pump",
            help="Enter device name for comprehensive analysis"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            lookback_months = st.slider("Lookback Period (months)", 1, 60, 12)
        with col2:
            include_risk = st.checkbox("Include Risk Assessment", value=True)
        
        if st.button("Analyze Device", type="primary") and device_name:
            with st.spinner("Analyzing device data..."):
                try:
                    intelligence = _get_device_intelligence(
                        device_name, lookback_months, include_risk
                    )
                    
                    # Display intelligence
                    _display_device_intelligence(intelligence, show_visualizations)
                    
                except Exception as e:
                    st.error(f"Device analysis failed: {str(e)}")
    
    with tab3:
        st.header("Trend Analysis")
        
        trend_query = st.text_input(
            "Query for Trend Analysis",
            placeholder="e.g., hip implant, cardiac device",
            help="Enter query to analyze trends over time"
        )
        
        time_periods = st.multiselect(
            "Time Periods",
            ["3months", "6months", "1year", "2years", "3years"],
            default=["6months", "1year", "2years"],
            help="Select time periods for trend analysis"
        )
        
        if st.button("Analyze Trends", type="primary") and trend_query:
            with st.spinner("Analyzing trends..."):
                try:
                    trends = _get_trend_analysis(trend_query, time_periods)
                    
                    # Display trends
                    _display_trend_analysis(trends, show_visualizations)
                    
                except Exception as e:
                    st.error(f"Trend analysis failed: {str(e)}")
    
    with tab4:
        st.header("Advanced Features")
        
        # Device comparison
        st.subheader("Device Comparison")
        devices_to_compare = st.text_area(
            "Devices to Compare (one per line)",
            placeholder="pacemaker\ninsulin pump\nhip implant",
            help="Enter device names to compare, one per line"
        )
        
        if st.button("Compare Devices") and devices_to_compare:
            device_list = [d.strip() for d in devices_to_compare.split('\n') if d.strip()]
            
            if len(device_list) >= 2:
                with st.spinner("Comparing devices..."):
                    try:
                        comparison = _compare_devices(device_list)
                        _display_device_comparison(comparison)
                    except Exception as e:
                        st.error(f"Device comparison failed: {str(e)}")
            else:
                st.warning("Please enter at least 2 devices to compare")
        
        # Manufacturer analysis
        st.subheader("Manufacturer Analysis")
        manufacturer_name = st.text_input(
            "Manufacturer Name",
            placeholder="e.g., Medtronic, Abbott, Johnson & Johnson",
            help="Enter manufacturer name for analysis"
        )
        
        if st.button("Analyze Manufacturer") and manufacturer_name:
            with st.spinner("Analyzing manufacturer data..."):
                try:
                    manufacturer_intel = _get_manufacturer_intelligence(manufacturer_name)
                    _display_manufacturer_intelligence(manufacturer_intel)
                except Exception as e:
                    st.error(f"Manufacturer analysis failed: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown("### About")
    st.info("""
    **Enhanced FDA Explorer** combines production-ready reliability with AI-powered insights 
    to provide comprehensive FDA medical device data exploration. This tool integrates multiple 
    FDA databases with intelligent analysis for researchers, regulatory professionals, and 
    healthcare organizations.
    
    **Features:**
    - 📊 Comprehensive data from 6 FDA databases
    - 🤖 AI-powered analysis and insights
    - 📈 Interactive visualizations
    - 🔍 Advanced search capabilities
    - ⚡ Real-time data processing
    """)


def _display_search_results(response, show_visualizations: bool, show_raw_data: bool):
    """Display search results"""
    
    # Summary metrics
    st.subheader("📊 Search Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Results", response.total_results)
    
    with col2:
        st.metric("Response Time", f"{response.response_time:.2f}s")
    
    with col3:
        st.metric("Data Sources", len(response.results))
    
    with col4:
        st.metric("Query Type", response.query_type.title())
    
    # Results by endpoint
    st.subheader("📋 Results by Data Source")
    
    for endpoint, df in response.results.items():
        if df.empty:
            continue
        
        with st.expander(f"{endpoint.upper()} ({len(df)} records)", expanded=True):
            
            # Summary
            st.write(f"**{len(df)} records** from {endpoint.upper()} database")
            
            # Visualizations
            if show_visualizations and len(df) > 0:
                _create_endpoint_visualizations(df, endpoint)
            
            # Raw data
            if show_raw_data:
                st.dataframe(df)
    
    # AI Analysis
    if response.ai_analysis:
        st.subheader("🤖 AI Analysis")
        
        analysis = response.ai_analysis
        
        # Summary
        if analysis.get('summary'):
            st.write("**Executive Summary:**")
            st.info(analysis['summary'])
        
        # Key findings
        if analysis.get('key_findings'):
            st.write("**Key Findings:**")
            for finding in analysis['key_findings']:
                st.write(f"• {finding}")
        
        # Risk assessment
        if analysis.get('risk_level'):
            risk_level = analysis['risk_level']
            risk_colors = {
                'LOW': 'green',
                'MEDIUM': 'yellow', 
                'HIGH': 'orange',
                'CRITICAL': 'red'
            }
            
            st.write(f"**Risk Level:** :{risk_colors.get(risk_level, 'gray')}[{risk_level}]")


def _create_endpoint_visualizations(df: pd.DataFrame, endpoint: str):
    """Create visualizations for endpoint data"""
    
    # Timeline visualization
    date_columns = [col for col in df.columns if 'date' in col.lower() and df[col].dtype == 'datetime64[ns]']
    
    if date_columns:
        date_col = date_columns[0]
        
        # Time series chart
        time_series = df[date_col].dt.to_period('M').value_counts().sort_index()
        
        fig = px.line(
            x=time_series.index.astype(str),
            y=time_series.values,
            title=f"{endpoint.upper()} Records Over Time",
            labels={'x': 'Month', 'y': 'Number of Records'}
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Category charts based on endpoint
    if endpoint.lower() == 'event':
        # Event type distribution
        if 'event_type' in df.columns:
            event_types = df['event_type'].value_counts().head(10)
            fig = px.bar(
                x=event_types.values,
                y=event_types.index,
                orientation='h',
                title="Top Event Types",
                labels={'x': 'Count', 'y': 'Event Type'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    elif endpoint.lower() == 'recall':
        # Recall classification
        if 'classification' in df.columns:
            classifications = df['classification'].value_counts()
            fig = px.pie(
                values=classifications.values,
                names=classifications.index,
                title="Recall Classifications"
            )
            st.plotly_chart(fig, use_container_width=True)


def _get_device_intelligence(device_name: str, lookback_months: int, include_risk: bool):
    """Get device intelligence (helper function)"""
    config = get_config_cached()
    
    # Create event loop if none exists
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    explorer = FDAExplorer(config)
    
    try:
        intelligence = loop.run_until_complete(
            explorer.get_device_intelligence(
                device_name=device_name,
                lookback_months=lookback_months,
                include_risk_assessment=include_risk
            )
        )
        return intelligence
    
    finally:
        explorer.close()


def _display_device_intelligence(intelligence: Dict[str, Any], show_visualizations: bool):
    """Display device intelligence"""
    
    device_name = intelligence["device_name"]
    data = intelligence["data"]
    
    st.subheader(f"📱 Device Intelligence: {device_name}")
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_records = sum(len(df) for df in data.values())
        st.metric("Total Records", total_records)
    
    with col2:
        data_sources = len([df for df in data.values() if not df.empty])
        st.metric("Data Sources", data_sources)
    
    with col3:
        lookback = intelligence["metadata"]["lookback_months"]
        st.metric("Lookback Period", f"{lookback} months")
    
    # Risk assessment
    if intelligence.get("risk_assessment"):
        risk = intelligence["risk_assessment"]
        
        st.subheader("⚠️ Risk Assessment")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Risk Score", f"{risk.overall_risk_score:.1f}/10")
        
        with col2:
            st.metric("Severity Level", risk.severity_level)
        
        with col3:
            st.metric("Confidence", f"{risk.confidence_score:.2f}")
        
        # Risk factors
        if risk.risk_factors:
            st.write("**Risk Factors:**")
            for factor in risk.risk_factors:
                st.write(f"• {factor}")
        
        # Recommendations
        if risk.recommendations:
            st.write("**Recommendations:**")
            for rec in risk.recommendations:
                st.write(f"• {rec}")
    
    # Data by endpoint
    st.subheader("📊 Data Breakdown")
    
    for endpoint, df in data.items():
        if df.empty:
            continue
        
        with st.expander(f"{endpoint} ({len(df)} records)", expanded=True):
            
            if show_visualizations:
                _create_endpoint_visualizations(df, endpoint)
            
            # Show sample data
            st.dataframe(df.head())


def _get_trend_analysis(query: str, time_periods: List[str]):
    """Get trend analysis (helper function)"""
    config = get_config_cached()
    
    # Create event loop if none exists
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    explorer = FDAExplorer(config)
    
    try:
        trends = loop.run_until_complete(
            explorer.get_trend_analysis(
                query=query,
                time_periods=time_periods
            )
        )
        return trends
    
    finally:
        explorer.close()


def _display_trend_analysis(trends: Dict[str, Any], show_visualizations: bool):
    """Display trend analysis"""
    
    query = trends["query"]
    trend_data = trends["trend_data"]
    
    st.subheader(f"📈 Trend Analysis: {query}")
    
    # Summary table
    summary_data = []
    for period, data in trend_data.items():
        total_records = sum(len(df) for df in data.values())
        summary_data.append({
            "Time Period": period,
            "Total Records": total_records,
            "Data Sources": len([df for df in data.values() if not df.empty])
        })
    
    st.dataframe(pd.DataFrame(summary_data))
    
    # Trend visualization
    if show_visualizations:
        # Create trend chart
        trend_chart_data = []
        for period, data in trend_data.items():
            total = sum(len(df) for df in data.values())
            trend_chart_data.append({
                "Period": period,
                "Records": total
            })
        
        chart_df = pd.DataFrame(trend_chart_data)
        
        fig = px.bar(
            chart_df,
            x="Period",
            y="Records",
            title=f"Trend Analysis: {query}",
            labels={"Records": "Number of Records"}
        )
        
        st.plotly_chart(fig, use_container_width=True)


def _compare_devices(device_list: List[str]):
    """Compare devices (helper function)"""
    config = get_config_cached()
    
    # Create event loop if none exists
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    explorer = FDAExplorer(config)
    
    try:
        comparison = loop.run_until_complete(
            explorer.compare_devices(
                device_names=device_list,
                lookback_months=12
            )
        )
        return comparison
    
    finally:
        explorer.close()


def _display_device_comparison(comparison: Dict[str, Any]):
    """Display device comparison"""
    
    devices = comparison["devices"]
    device_data = comparison["device_data"]
    
    st.subheader(f"⚖️ Device Comparison: {', '.join(devices)}")
    
    # Comparison table
    comparison_table = []
    for device_name, device_info in device_data.items():
        total_records = sum(len(df) for df in device_info["data"].values())
        risk_score = device_info.get("risk_assessment", {}).get("overall_risk_score", "N/A")
        
        comparison_table.append({
            "Device": device_name,
            "Total Records": total_records,
            "Risk Score": risk_score,
            "Data Sources": len([df for df in device_info["data"].values() if not df.empty])
        })
    
    st.dataframe(pd.DataFrame(comparison_table))
    
    # Comparison analysis
    if comparison.get("comparison_analysis"):
        st.subheader("📊 Comparison Analysis")
        analysis = comparison["comparison_analysis"]
        
        if analysis.get("summary"):
            st.info(analysis["summary"])


def _get_manufacturer_intelligence(manufacturer_name: str):
    """Get manufacturer intelligence (helper function)"""
    config = get_config_cached()
    
    # Create event loop if none exists
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    explorer = FDAExplorer(config)
    
    try:
        intelligence = loop.run_until_complete(
            explorer.get_manufacturer_intelligence(
                manufacturer_name=manufacturer_name,
                lookback_months=12
            )
        )
        return intelligence
    
    finally:
        explorer.close()


def _display_manufacturer_intelligence(intelligence: Dict[str, Any]):
    """Display manufacturer intelligence"""
    
    manufacturer_name = intelligence["manufacturer_name"]
    search_response = intelligence["search_response"]
    
    st.subheader(f"🏭 Manufacturer Intelligence: {manufacturer_name}")
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Results", search_response.total_results)
    
    with col2:
        st.metric("Data Sources", len(search_response.results))
    
    with col3:
        st.metric("Response Time", f"{search_response.response_time:.2f}s")
    
    # Results by endpoint
    for endpoint, df in search_response.results.items():
        if df.empty:
            continue
        
        with st.expander(f"{endpoint.upper()} ({len(df)} records)", expanded=True):
            st.dataframe(df.head())


if __name__ == "__main__":
    main()