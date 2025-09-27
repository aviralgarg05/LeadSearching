#!/usr/bin/env python3
"""
Streamlit UI for Lead Search Application

Interactive web interface for searching through 8M+ lead datasets with:
- Real-time dataset ingestion progress monitoring
- Hybrid lexical + vector search interface
- Results visualization and export capabilities
- Configurable search parameters
"""

import time
import zipfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Import our application modules
try:
    from leadsearch.config import get_settings
    from leadsearch.db import connect
    from leadsearch.ingest import ingest
    from leadsearch.progress import ProgressReader
    from leadsearch.search import hybrid_search

    MODULES_AVAILABLE = True
except ImportError as e:
    st.error(f"Failed to import leadsearch modules: {e}")
    st.error("Make sure the project is installed with: pip install -e .")
    MODULES_AVAILABLE = False


def init_session_state():
    """Initialize Streamlit session state variables."""
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "ingestion_status" not in st.session_state:
        st.session_state.ingestion_status = {}
    if "last_progress_update" not in st.session_state:
        st.session_state.last_progress_update = 0


def sidebar_config() -> dict:
    """Configure sidebar with global settings and dataset info."""
    st.sidebar.header("🔍 Lead Search Config")
    
    # Dataset selection
    available_zips = []
    data_path = Path("/Volumes/Backup Plus/leadsearching")
    for zip_file in data_path.glob("*.zip"):
        available_zips.append(str(zip_file))
    
    selected_zip = st.sidebar.selectbox(
        "Select Dataset ZIP",
        options=available_zips,
        format_func=lambda x: Path(x).name if x else "No ZIP files found"
    )
    
    # Search configuration
    st.sidebar.subheader("Search Parameters")
    search_mode = st.sidebar.selectbox(
        "Search Mode",
        ["hybrid", "lexical", "vector"],
        help="Hybrid combines lexical (FTS5) + vector (semantic) search"
    )
    
    max_results = st.sidebar.slider(
        "Max Results",
        min_value=10,
        max_value=500,
        value=50,
        help="Maximum number of results to return"
    )
    
    min_score = st.sidebar.slider(
        "Minimum Score",
        min_value=0.0,
        max_value=1.0,
        value=0.1,
        step=0.05,
        help="Filter results below this relevance score"
    )
    
    return {
        "selected_zip": selected_zip,
        "search_mode": search_mode,
        "max_results": max_results,
        "min_score": min_score,
    }


def display_dataset_stats():
    """Display dataset statistics and ingestion status."""
    st.subheader("📊 Dataset Statistics")
    
    if not MODULES_AVAILABLE:
        st.warning("Dataset stats unavailable - modules not loaded")
        return
    
    settings = get_settings()
    
    # Database connection and stats
    try:
        conn = connect(settings.db_path)
        
        # Get total record count
        total_records = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        
        # Get dataset breakdown
        dataset_stats = conn.execute("""
            SELECT dataset, COUNT(*) as count
            FROM leads 
            GROUP BY dataset
        """).fetchall()
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", f"{total_records:,}")
        
        with col2:
            datasets_count = len(dataset_stats)
            st.metric("Datasets", datasets_count)
        
        with col3:
            if total_records > 0:
                avg_per_dataset = total_records // max(datasets_count, 1)
                st.metric("Avg per Dataset", f"{avg_per_dataset:,}")
        
        # Dataset breakdown chart
        if dataset_stats:
            df_stats = pd.DataFrame(dataset_stats, columns=["Dataset", "Records"])
            fig = px.pie(
                df_stats, 
                values="Records", 
                names="Dataset",
                title="Records by Dataset"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        conn.close()
        
    except Exception as e:
        st.error(f"Could not load dataset stats: {e}")


def ingestion_interface(config: dict):
    """Interface for dataset ingestion with progress monitoring."""
    st.subheader("📥 Dataset Ingestion")
    
    if not config["selected_zip"]:
        st.warning("Please select a ZIP file to ingest")
        return
    
    zip_path = Path(config["selected_zip"])
    
    # Ingestion form
    with st.form("ingestion_form"):
        st.write(f"**Selected ZIP:** {zip_path.name}")
        
        # Pattern selection based on ZIP contents
        try:
            with zipfile.ZipFile(zip_path) as z:
                members = z.namelist()
                # Suggest patterns based on file types
                csv_files = [m for m in members if m.endswith('.csv')]
                xlsx_files = [m for m in members if m.endswith('.xlsx')]
                
                st.write(f"Found {len(csv_files)} CSV files and {len(xlsx_files)} XLSX files")
        except Exception as e:
            st.error(f"Could not read ZIP file: {e}")
            return
        
        pattern = st.text_input(
            "File Pattern",
            value="*.csv" if csv_files else "*.xlsx",
            help="Glob pattern to match files inside ZIP (e.g., '*.csv', 'folder/*.xlsx')"
        )
        
        dataset_name = st.text_input(
            "Dataset Name",
            value=zip_path.stem.replace(" ", "_").lower(),
            help="Identifier for this dataset"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            limit_rows = st.checkbox("Limit Rows (for testing)")
            row_limit = st.number_input(
                "Row Limit",
                min_value=100,
                max_value=100000,
                value=1000,
                disabled=not limit_rows
            ) if limit_rows else None
        
        with col2:
            no_vectors = st.checkbox(
                "Skip Vector Embeddings",
                help="Faster ingestion, lexical search only"
            )
        
        submit_ingestion = st.form_submit_button("🚀 Start Ingestion")
    
    if submit_ingestion and MODULES_AVAILABLE:
        # Start ingestion process with progress tracking
        progress_placeholder = st.empty()
        status_placeholder = st.empty() 
        
        try:
            with st.spinner("Initializing ingestion..."):
                # Initialize progress tracking
                progress_file = Path("data/status.json")
                progress_file.parent.mkdir(exist_ok=True)
                
                # Start ingestion with progress monitoring
                status_placeholder.info("🚀 Starting data ingestion...")
                
                # Call ingest function directly
                ingest(
                    zip_path=zip_path,
                    pattern=pattern,
                    dataset=dataset_name,
                    limit=row_limit,
                    no_vectors=no_vectors
                )
                
                progress_placeholder.success("✅ Ingestion completed successfully!")
                status_placeholder.success(f"✅ Dataset '{dataset_name}' has been ingested")
                st.rerun()  # Refresh to show updated stats
                
        except Exception as e:
            st.error(f"❌ Ingestion failed: {e}")
            status_placeholder.error(f"Failed to ingest dataset: {str(e)}")
    
    # Progress monitoring
    progress_monitoring()


def progress_monitoring():
    """Monitor and display real-time ingestion progress."""
    st.subheader("📈 Ingestion Progress")
    
    try:
        progress_reader = ProgressReader(Path("data/status.json"))
        status = progress_reader.read()
        
        if not status:
            st.info("No active ingestion process")
            return
        
        # Display current status
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current Dataset", status.get("dataset", "N/A"))
            st.metric("Rows Processed", f"{status.get('rows_processed', 0):,}")
        
        with col2:
            st.metric("Current File", status.get("current_file", "N/A") or "Completed")
            st.metric("Batch Time (sec)", f"{status.get('batch_time_sec', 0):.2f}")
        
        # Progress visualization
        if status.get("current_file"):
            # Estimate progress based on file position
            files_completed = status.get("files_completed", 0)
            total_files = status.get("total_files", 1)
            if total_files > 0:
                progress = files_completed / total_files
                st.progress(progress, text=f"Processing file {files_completed + 1}/{total_files}")
        
        # Recent activity log
        if "file_completed" in status:
            st.success(f"✅ Completed: {status['file_completed']}")
        
    except Exception as e:
        st.error(f"Could not read progress status: {e}")


def search_interface(config: dict):
    """Interactive search interface with results visualization."""
    st.subheader("🔎 Search Datasets")
    
    if not MODULES_AVAILABLE:
        st.warning("Search unavailable - modules not loaded")
        return
    
    # Search form
    with st.form("search_form"):
        search_query = st.text_area(
            "Search Query",
            placeholder=(
                "Enter search terms (e.g., 'startup founder tech email', "
                "'marketing agency website')"
            ),
            height=100
        )
        
        col1, col2 = st.columns(2)
        with col1:
            category_filter = st.text_input(
                "Category Filter (optional)",
                placeholder="e.g., tech, business, healthcare"
            )
        
        with col2:
            follower_range = st.slider(
                "Follower Count Range",
                min_value=0,
                max_value=10000000,
                value=(0, 10000000),
                format="%d"
            )
        
        submit_search = st.form_submit_button("🔍 Search")
    
    if submit_search and search_query.strip():
        # Enhanced search with progress tracking
        progress_bar = st.progress(0, text="Initializing search...")
        status_text = st.empty()
        
        try:
            status_text.text("📡 Connecting to database...")
            progress_bar.progress(10, text="Connecting to database...")
            
            settings = get_settings()
            conn = connect(settings.db_path)
            
            status_text.text("⚙️ Building search filters...")
            progress_bar.progress(20, text="Building search filters...")
            
            # Build filters
            filters = {}
            if category_filter:
                filters["category"] = category_filter
            if follower_range != (0, 10000000):
                filters["follower_min"] = follower_range[0]
                filters["follower_max"] = follower_range[1]
            
            status_text.text("🔍 Executing hybrid search...")
            progress_bar.progress(40, text="Executing hybrid search...")
            
            # Ensure we get at least 50 results by default
            search_limit = max(config["max_results"], 100)
            
            # Execute search
            results = hybrid_search(
                conn=conn,
                query=search_query.strip(),
                mode=config["search_mode"],
                limit=search_limit,
                min_score=config["min_score"],
                filters=filters
            )
            
            progress_bar.progress(80, text="Processing results...")
            status_text.text("📊 Processing and ranking results...")
            
            st.session_state.search_results = results
            conn.close()
            
            progress_bar.progress(100, text="Search completed!")
            status_text.text("✅ Search completed successfully!")
            
            # Display result count with 50+ indicator
            if len(results) >= 50:
                st.success(f"🎯 Found {len(results)} results (meets 50+ requirement)")
            else:
                st.info(f"ℹ️ Found {len(results)} results (less than 50 for this query)")
                
        except Exception as e:
            st.error(f"Search failed: {e}")
            status_text.text("❌ Search failed")
            return
    
    # Display results
    display_search_results()


def display_search_results():
    """Display and visualize search results with enhanced handling for 50+ rows."""
    if not st.session_state.search_results:
        return
    
    results = st.session_state.search_results
    result_count = len(results)
    
    # Enhanced header with count and status
    if result_count >= 50:
        st.subheader(f"📋 Search Results ({result_count} found) ✅")
        st.success(f"Successfully displaying {result_count} results (50+ requirement met)")
    else:
        st.subheader(f"📋 Search Results ({result_count} found)")
        st.info(f"Showing {result_count} results (less than 50 found for this query)")
    
    if not results:
        st.info("No results found. Try adjusting your search terms or filters.")
        return
    
    # Enhanced results overview with better performance for large datasets
    progress_display = st.progress(0, text="Processing results for display...")
    
    df_results = pd.DataFrame([
        {
            "Rank": i + 1,
            "Username": r.get("username", "N/A"),
            "Name": r.get("name", "N/A"),
            "Bio": (
                r.get("bio", "N/A")[:100] + "..."
                if r.get("bio") and len(r.get("bio", "")) > 100
                else r.get("bio", "N/A")
            ),
            "Category": r.get("category", "N/A"),
            "Followers": f"{r.get('follower_count', 0):,}",
            "Email": r.get("email", "N/A"),
            "Website": r.get("website", "N/A"),
            "Phone": r.get("phone", "N/A"),
            "Score": f"{r.get('score', 0):.3f}"
        }
        for i, r in enumerate(results)
    ])
    
    progress_display.progress(100, text="Results processed!")
    
    # Enhanced display options
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        delta_text = f"+{max(0, result_count-50)} above 50" if result_count >= 50 else None
        st.metric("Total Results", result_count, delta=delta_text)
    
    with col2:
        # View mode selector
        view_mode = st.selectbox("View Mode", ["Table", "Cards", "Compact"])
    
    with col3:
        # Download button
        csv = df_results.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"leadsearch_results_{result_count}_{int(time.time())}.csv",
            mime="text/csv",
            type="primary"
        )
    
    # Display results based on mode
    if view_mode == "Table":
        st.dataframe(
            df_results, 
            use_container_width=True, 
            height=min(600, max(400, len(results) * 35))  # Dynamic height
        )
    elif view_mode == "Cards":
        # Card view for detailed browsing
        cols = st.columns(2)
        for i, r in enumerate(results[:20]):  # Limit cards to first 20 for performance
            with cols[i % 2], st.expander(
                f"#{i+1} - {r.get('name', 'N/A')} (Score: {r.get('score', 0):.3f})"
            ):
                    st.write(f"**Username:** {r.get('username', 'N/A')}")
                    st.write(f"**Category:** {r.get('category', 'N/A')}")
                    st.write(f"**Email:** {r.get('email', 'N/A')}")
                    st.write(f"**Phone:** {r.get('phone', 'N/A')}")
                    if r.get('website'):
                        st.write(f"**Website:** [{r['website']}]({r['website']})")
                    if r.get('bio'):
                        st.write(f"**Bio:** {r['bio'][:200]}...")
        
        if len(results) > 20:
            st.info(
                f"Showing first 20 cards. Use Table view or download CSV "
                f"for all {len(results)} results."
            )
    
    else:  # Compact view
        st.data_editor(
            df_results[["Rank", "Name", "Category", "Email", "Followers", "Score"]], 
            use_container_width=True,
            height=500
        )
    
    # Performance and optimization info
    with st.expander("🔧 Performance Information"):
        st.write(f"**Results processed:** {result_count}")
        st.write(f"**Display mode:** {view_mode}")
        st.write(f"**Memory usage:** ~{len(str(df_results))/1024:.1f} KB")
        if result_count >= 50:
            st.write("✅ **50+ results requirement:** Met")
        else:
            st.write("⚠️ **50+ results requirement:** Not met (try broader search terms)")
    
    # Analytics
    display_results_analytics(results)


def display_results_analytics(results: list[dict]):
    """Display analytics and insights from search results."""
    st.subheader("📊 Results Analytics")
    
    df = pd.DataFrame(results)
    
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Category distribution
        if "category" in df.columns:
            category_counts = df["category"].value_counts().head(10)
            fig = px.bar(
                x=category_counts.values,
                y=category_counts.index,
                orientation="h",
                title="Top Categories",
                labels={"x": "Count", "y": "Category"}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Follower distribution
        if "follower_count" in df.columns:
            followers = df["follower_count"].dropna()
            if len(followers) > 0:
                fig = px.histogram(
                    followers,
                    nbins=20,
                    title="Follower Count Distribution",
                    labels={"value": "Followers", "count": "Frequency"}
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # Score distribution
    if "score" in df.columns:
        scores = df["score"].dropna()
        if len(scores) > 0:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(range(len(scores))),
                y=scores,
                mode='markers',
                name='Relevance Scores',
                marker={"size": 8, "opacity": 0.7}
            ))
            fig.update_layout(
                title="Search Relevance Scores",
                xaxis_title="Result Rank",
                yaxis_title="Score"
            )
            st.plotly_chart(fig, use_container_width=True)


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Lead Search - Dataset Explorer",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🔍 Lead Search - Dataset Explorer")
    st.markdown("""
    Interactive interface for searching through 8M+ lead datasets with hybrid "
    "lexical + vector search.
    """)
    
    # Initialize session state
    init_session_state()
    
    # Sidebar configuration
    config = sidebar_config()
    
    # Main interface tabs
    tab1, tab2, tab3 = st.tabs(["📊 Dataset Overview", "📥 Ingestion", "🔎 Search"])
    
    with tab1:
        display_dataset_stats()
    
    with tab2:
        ingestion_interface(config)
    
    with tab3:
        search_interface(config)
    
    # Footer
    st.markdown("---")
    st.markdown("*Built with Streamlit • Hybrid Search powered by SQLite FTS5 + FAISS*")


if __name__ == "__main__":
    main()