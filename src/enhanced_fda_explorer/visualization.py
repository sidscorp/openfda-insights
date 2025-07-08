"""
Data visualization components for Enhanced FDA Explorer
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import seaborn as sns
import matplotlib.pyplot as plt


class DataVisualizer:
    """
    Data visualization engine for FDA Explorer.
    
    Provides interactive visualizations for FDA data analysis including:
    - Time series analysis
    - Risk assessment charts
    - Comparative analysis
    - Trend visualizations
    - Regulatory timeline charts
    """
    
    def __init__(self):
        """Initialize the data visualizer"""
        self.color_palette = {
            'primary': '#1f77b4',
            'secondary': '#ff7f0e',
            'success': '#2ca02c',
            'warning': '#d62728',
            'info': '#9467bd',
            'danger': '#8c564b'
        }
    
    def create_timeline_chart(self, df: pd.DataFrame, date_column: str, 
                            title: str = "Timeline Analysis") -> go.Figure:
        """
        Create timeline visualization for FDA data.
        
        Args:
            df: DataFrame with temporal data
            date_column: Name of the date column
            title: Chart title
            
        Returns:
            Plotly figure object
        """
        # Prepare data
        df_copy = df.copy()
        df_copy[date_column] = pd.to_datetime(df_copy[date_column])
        
        # Group by month
        monthly_data = df_copy.groupby(df_copy[date_column].dt.to_period('M')).size()
        
        # Create line chart
        fig = px.line(
            x=monthly_data.index.astype(str),
            y=monthly_data.values,
            title=title,
            labels={'x': 'Month', 'y': 'Number of Records'}
        )
        
        # Customize layout
        fig.update_layout(
            xaxis_title="Time Period",
            yaxis_title="Number of Records",
            hovermode='x unified',
            showlegend=False
        )
        
        return fig
    
    def create_risk_assessment_chart(self, risk_data: Dict[str, Any]) -> go.Figure:
        """
        Create risk assessment visualization.
        
        Args:
            risk_data: Risk assessment data
            
        Returns:
            Plotly figure object
        """
        # Create gauge chart for risk score
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=risk_data.get('overall_risk_score', 0),
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Risk Score"},
            delta={'reference': 5},
            gauge={
                'axis': {'range': [None, 10]},
                'bar': {'color': self._get_risk_color(risk_data.get('overall_risk_score', 0))},
                'steps': [
                    {'range': [0, 3], 'color': "lightgreen"},
                    {'range': [3, 6], 'color': "yellow"},
                    {'range': [6, 8], 'color': "orange"},
                    {'range': [8, 10], 'color': "red"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 8
                }
            }
        ))
        
        fig.update_layout(
            title="Risk Assessment",
            height=400
        )
        
        return fig
    
    def create_categorical_chart(self, df: pd.DataFrame, column: str, 
                               chart_type: str = "bar", title: str = None) -> go.Figure:
        """
        Create categorical data visualization.
        
        Args:
            df: DataFrame with categorical data
            column: Column name for categorization
            chart_type: Type of chart (bar, pie, horizontal_bar)
            title: Chart title
            
        Returns:
            Plotly figure object
        """
        # Get value counts
        value_counts = df[column].value_counts().head(10)
        
        if not title:
            title = f"{column.replace('_', ' ').title()} Distribution"
        
        if chart_type == "bar":
            fig = px.bar(
                x=value_counts.index,
                y=value_counts.values,
                title=title,
                labels={'x': column.replace('_', ' ').title(), 'y': 'Count'}
            )
        elif chart_type == "pie":
            fig = px.pie(
                values=value_counts.values,
                names=value_counts.index,
                title=title
            )
        elif chart_type == "horizontal_bar":
            fig = px.bar(
                x=value_counts.values,
                y=value_counts.index,
                orientation='h',
                title=title,
                labels={'x': 'Count', 'y': column.replace('_', ' ').title()}
            )
        else:
            raise ValueError(f"Unsupported chart type: {chart_type}")
        
        return fig
    
    def create_comparison_chart(self, comparison_data: Dict[str, Any], 
                              metric: str = "total_records") -> go.Figure:
        """
        Create comparison visualization for multiple items.
        
        Args:
            comparison_data: Dictionary with comparison data
            metric: Metric to compare
            
        Returns:
            Plotly figure object
        """
        # Prepare data for comparison
        items = list(comparison_data.keys())
        values = [comparison_data[item].get(metric, 0) for item in items]
        
        # Create bar chart
        fig = px.bar(
            x=items,
            y=values,
            title=f"Comparison: {metric.replace('_', ' ').title()}",
            labels={'x': 'Items', 'y': metric.replace('_', ' ').title()}
        )
        
        # Customize layout
        fig.update_layout(
            xaxis_tickangle=-45,
            showlegend=False
        )
        
        return fig
    
    def create_trend_analysis_chart(self, trend_data: Dict[str, Any]) -> go.Figure:
        """
        Create trend analysis visualization.
        
        Args:
            trend_data: Trend data by time periods
            
        Returns:
            Plotly figure object
        """
        # Prepare data
        periods = list(trend_data.keys())
        values = [sum(len(df) for df in data.values()) for data in trend_data.values()]
        
        # Create line chart
        fig = px.line(
            x=periods,
            y=values,
            title="Trend Analysis Over Time",
            labels={'x': 'Time Period', 'y': 'Number of Records'},
            markers=True
        )
        
        # Add trend line
        if len(values) > 1:
            # Calculate trend
            x_numeric = list(range(len(periods)))
            z = np.polyfit(x_numeric, values, 1)
            p = np.poly1d(z)
            
            fig.add_scatter(
                x=periods,
                y=p(x_numeric),
                mode='lines',
                name='Trend Line',
                line=dict(dash='dash', color='red')
            )
        
        return fig
    
    def create_regulatory_timeline(self, timeline_events: List[Dict[str, Any]]) -> go.Figure:
        """
        Create regulatory timeline visualization.
        
        Args:
            timeline_events: List of timeline events
            
        Returns:
            Plotly figure object
        """
        if not timeline_events:
            return go.Figure()
        
        # Prepare data
        df = pd.DataFrame(timeline_events)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Create timeline
        fig = px.scatter(
            df,
            x='date',
            y='event_type',
            color='source',
            size_max=10,
            title="Regulatory Timeline",
            hover_data=['description']
        )
        
        # Customize layout
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Event Type",
            showlegend=True
        )
        
        return fig
    
    def create_heatmap(self, data: pd.DataFrame, x_column: str, 
                      y_column: str, value_column: str = None) -> go.Figure:
        """
        Create heatmap visualization.
        
        Args:
            data: DataFrame with data
            x_column: Column for x-axis
            y_column: Column for y-axis
            value_column: Column for values (optional)
            
        Returns:
            Plotly figure object
        """
        if value_column:
            # Pivot data for heatmap
            pivot_data = data.pivot_table(
                index=y_column,
                columns=x_column,
                values=value_column,
                aggfunc='count',
                fill_value=0
            )
        else:
            # Create count-based heatmap
            pivot_data = data.groupby([y_column, x_column]).size().unstack(fill_value=0)
        
        # Create heatmap
        fig = px.imshow(
            pivot_data.values,
            x=pivot_data.columns,
            y=pivot_data.index,
            color_continuous_scale='Viridis',
            title="Data Heatmap"
        )
        
        return fig
    
    def create_multi_endpoint_comparison(self, results: Dict[str, pd.DataFrame]) -> go.Figure:
        """
        Create multi-endpoint comparison visualization.
        
        Args:
            results: Results by endpoint
            
        Returns:
            Plotly figure object
        """
        # Prepare data
        endpoints = list(results.keys())
        record_counts = [len(df) for df in results.values()]
        
        # Create bar chart
        fig = px.bar(
            x=endpoints,
            y=record_counts,
            title="Records by Data Source",
            labels={'x': 'Data Source', 'y': 'Number of Records'}
        )
        
        # Customize colors
        fig.update_traces(
            marker_color=[self.color_palette['primary'] if count > 0 else '#cccccc' 
                         for count in record_counts]
        )
        
        return fig
    
    def create_summary_dashboard(self, data: Dict[str, Any]) -> List[go.Figure]:
        """
        Create summary dashboard with multiple visualizations.
        
        Args:
            data: Dictionary with various data sources
            
        Returns:
            List of Plotly figures
        """
        figures = []
        
        # 1. Overview metrics
        if 'results' in data:
            fig1 = self.create_multi_endpoint_comparison(data['results'])
            figures.append(fig1)
        
        # 2. Timeline analysis
        if 'timeline_events' in data:
            fig2 = self.create_regulatory_timeline(data['timeline_events'])
            figures.append(fig2)
        
        # 3. Risk assessment
        if 'risk_assessment' in data:
            fig3 = self.create_risk_assessment_chart(data['risk_assessment'])
            figures.append(fig3)
        
        # 4. Trend analysis
        if 'trend_data' in data:
            fig4 = self.create_trend_analysis_chart(data['trend_data'])
            figures.append(fig4)
        
        return figures
    
    def create_interactive_dashboard(self, data: Dict[str, Any]) -> go.Figure:
        """
        Create interactive dashboard with subplots.
        
        Args:
            data: Dictionary with various data sources
            
        Returns:
            Plotly figure with subplots
        """
        # Create subplots
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=('Data Sources', 'Timeline', 'Risk Assessment', 'Trends'),
            specs=[[{"type": "bar"}, {"type": "scatter"}],
                   [{"type": "indicator"}, {"type": "scatter"}]]
        )
        
        # Add plots to subplots
        if 'results' in data:
            endpoints = list(data['results'].keys())
            counts = [len(df) for df in data['results'].values()]
            
            fig.add_trace(
                go.Bar(x=endpoints, y=counts, name="Data Sources"),
                row=1, col=1
            )
        
        # Add other subplots as needed...
        
        fig.update_layout(
            title="FDA Data Analysis Dashboard",
            showlegend=False,
            height=800
        )
        
        return fig
    
    def _get_risk_color(self, risk_score: float) -> str:
        """Get color based on risk score"""
        if risk_score < 3:
            return "green"
        elif risk_score < 6:
            return "yellow"
        elif risk_score < 8:
            return "orange"
        else:
            return "red"
    
    def export_chart(self, fig: go.Figure, filename: str, format: str = "png"):
        """
        Export chart to file.
        
        Args:
            fig: Plotly figure
            filename: Output filename
            format: Export format (png, pdf, svg, html)
        """
        if format == "html":
            fig.write_html(filename)
        elif format == "png":
            fig.write_image(filename)
        elif format == "pdf":
            fig.write_image(filename)
        elif format == "svg":
            fig.write_image(filename)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def create_report_charts(self, data: Dict[str, Any]) -> Dict[str, go.Figure]:
        """
        Create a comprehensive set of charts for reporting.
        
        Args:
            data: Dictionary with analysis data
            
        Returns:
            Dictionary of named figures
        """
        charts = {}
        
        # Main search results
        if 'results' in data:
            charts['overview'] = self.create_multi_endpoint_comparison(data['results'])
        
        # Timeline analysis
        if 'timeline_events' in data:
            charts['timeline'] = self.create_regulatory_timeline(data['timeline_events'])
        
        # Risk assessment
        if 'risk_assessment' in data:
            charts['risk'] = self.create_risk_assessment_chart(data['risk_assessment'])
        
        # Trends
        if 'trend_data' in data:
            charts['trends'] = self.create_trend_analysis_chart(data['trend_data'])
        
        # Comparison
        if 'comparison_data' in data:
            charts['comparison'] = self.create_comparison_chart(data['comparison_data'])
        
        return charts


# Utility functions for visualization
def format_large_numbers(value: float) -> str:
    """Format large numbers for display"""
    if value >= 1000000:
        return f"{value/1000000:.1f}M"
    elif value >= 1000:
        return f"{value/1000:.1f}K"
    else:
        return str(int(value))


def get_color_scale(values: List[float], colorscale: str = "Viridis") -> List[str]:
    """Get color scale for values"""
    import plotly.colors as pc
    
    if not values:
        return []
    
    # Normalize values
    min_val, max_val = min(values), max(values)
    if min_val == max_val:
        return [pc.qualitative.Plotly[0]] * len(values)
    
    normalized = [(v - min_val) / (max_val - min_val) for v in values]
    
    # Get colors from colorscale
    colors = []
    for norm_val in normalized:
        color_idx = int(norm_val * (len(pc.sequential.Viridis) - 1))
        colors.append(pc.sequential.Viridis[color_idx])
    
    return colors


def create_summary_table(data: Dict[str, Any]) -> pd.DataFrame:
    """Create summary table from data"""
    summary_data = []
    
    for key, value in data.items():
        if isinstance(value, pd.DataFrame):
            summary_data.append({
                'Data Source': key,
                'Records': len(value),
                'Columns': len(value.columns),
                'Memory Usage': f"{value.memory_usage(deep=True).sum() / 1024:.1f} KB"
            })
        elif isinstance(value, dict):
            summary_data.append({
                'Data Source': key,
                'Records': len(value),
                'Columns': 'N/A',
                'Memory Usage': 'N/A'
            })
    
    return pd.DataFrame(summary_data)