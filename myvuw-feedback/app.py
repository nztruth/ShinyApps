from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from shinywidgets import render_plotly, output_widget
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import pyodide_http
from plotly.subplots import make_subplots
import warnings
import sys
import os

pyodide_http.patch_all()
warnings.filterwarnings('ignore')


# Function to load CSV files in Shinylive environment
def load_csv_shinylive(filename):
    """Load CSV file compatible with Shinylive environment"""
    try:
        # Try different possible paths
        paths_to_try = [
            filename,  # Current directory
            f'./{filename}',  # Explicit current directory
            f'/home/pyodide/{filename}',  # Pyodide home
            f'/home/web_user/{filename}',  # Alternative home
        ]

        # Also check if we're in a specific app directory
        if hasattr(sys, 'path') and len(sys.path) > 0:
            app_dir = sys.path[0]
            if app_dir:
                paths_to_try.append(os.path.join(app_dir, filename))

        for path in paths_to_try:
            try:
                df = pd.read_csv(path)
                print(f"Successfully loaded {filename} from {path}")
                return df
            except:
                continue

        # If all paths fail, try using pyodide's fetch mechanism
        try:
            from pyodide.http import open_url
            url = f'./{filename}'
            df = pd.read_csv(open_url(url))
            print(f"Successfully loaded {filename} using open_url")
            return df
        except:
            pass

        raise FileNotFoundError(f"Could not find {filename} in any location")

    except Exception as e:
        print(f"Error loading {filename}: {str(e)}")
        raise


# Load the data with error handling
try:
    feedback_df = load_csv_shinylive('tbl_AllFeedback.csv')
    avg_feedback_df = load_csv_shinylive('qry_AverageFeedback.csv')
except FileNotFoundError as e:
    print("=" * 60)
    print("ERROR: Required CSV files not found!")
    print("=" * 60)
    print("Please ensure the following files are in the same directory as app.py:")
    print("  - tbl_AllFeedback.csv")
    print("  - qry_AverageFeedback.csv")
    print("=" * 60)
    print(f"Error details: {e}")

    # Create dummy data for demonstration if files not found
    print("\nCreating dummy data for demonstration purposes...")

    # Create dummy feedback_df
    years = [2020, 2021, 2022, 2023]
    courses = ['COMP101', 'COMP102', 'MATH101', 'PHYS101', 'CHEM101']

    data = []
    for year in years:
        for course in courses:
            data.append({
                'Year': year,
                'Course Code': course,
                'Course Title': f'{course} - Introduction to {course[:-3]}',
                'Course Letter': course[:4],
                'Responses': np.random.randint(20, 100),
                'Enrolled': np.random.randint(50, 150),
                'Low Sample': np.random.choice([True, False], p=[0.2, 0.8]),
                'Q1: Well-organised': np.random.uniform(1.5, 4.5),
                'Q2: Clear communication': np.random.uniform(1.5, 4.5),
                'Q3: Assessment helped': np.random.uniform(1.5, 4.5),
                'Q4: Helpful feedback': np.random.uniform(1.5, 4.5),
                'Q5: Workload (3=ideal)': np.random.uniform(2.0, 4.0),
                'Q6: Understanding': np.random.uniform(1.5, 4.5),
                'Q7: Interest': np.random.uniform(1.5, 4.5),
                'Q8: Valuable': np.random.uniform(1.5, 4.5),
                'Q9: Overall quality': np.random.uniform(1.5, 4.5),
            })

    feedback_df = pd.DataFrame(data)
    avg_feedback_df = feedback_df.groupby('Course Code').mean().reset_index()

    print("Dummy data created successfully!")

# Prepare data - remove rank columns
rank_columns = [col for col in feedback_df.columns if 'Rank' in col]
feedback_df = feedback_df.drop(columns=rank_columns)

feedback_df['Course Full'] = feedback_df['Course Code'] + ' - ' + feedback_df['Course Title']
feedback_df['Response Rate'] = (feedback_df['Responses'] / feedback_df['Enrolled'] * 100).round(1)
years = sorted(feedback_df['Year'].unique())
course_letters = sorted(feedback_df['Course Letter'].unique())

# Question mapping
QUESTION_SHORT = {
    'Q1: Well-organised': 'Organisation',
    'Q2: Clear communication': 'Communication',
    'Q3: Assessment helped': 'Assessment',
    'Q4: Helpful feedback': 'Feedback',
    'Q5: Workload (3=ideal)': 'Workload',
    'Q6: Understanding': 'Understanding',
    'Q7: Interest': 'Interest',
    'Q8: Valuable': 'Value',
    'Q9: Overall quality': 'Overall'
}

# Color palette
COLORS = {
    'primary': '#3498db',
    'success': '#2ecc71',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'info': '#16a085',
    'dark': '#2c3e50',
    'light': '#ecf0f1',
    'gradient': ['#3498db', '#2ecc71', '#f39c12', '#e74c3c', '#9b59b6']
}


# Create shared filter sidebar
def create_filter_sidebar():
    return ui.sidebar(
        ui.h4("Filters", class_="mb-3"),
        ui.input_select(
            "year_filter",
            "Year(s):",
            choices=["All"] + [str(y) for y in years],
            selected="All",
            multiple=True
        ),
        ui.input_select(
            "dept_filter",
            "Department(s):",
            choices=["All"] + course_letters,
            selected="All",
            multiple=True
        ),
        ui.input_slider(
            "response_filter",
            "Min Responses:",
            min=0,
            max=100,
            value=10,
            step=5
        ),
        ui.input_switch(
            "exclude_low_sample",
            "Exclude Low Sample",
            value=True
        ),
        ui.hr(),
        ui.div(
            ui.p("Filters apply to all pages", class_="text-muted small"),
            ui.p("Data updates automatically", class_="text-muted small")
        ),
        width=250,
        style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;"
    )


# Define the UI
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Overview",
        ui.div(
            ui.h2("Victoria University of Wellington Course Feedback Dashboard", class_="text-center mb-4"),
            ui.p("Interactive analysis of student course feedback data", class_="text-center text-muted mb-4"),
            class_="container"
        ),
        ui.layout_columns(
            ui.card(
                ui.card_header("Key Performance Indicators"),
                ui.layout_columns(
                    ui.value_box(
                        "Total Courses",
                        ui.output_text("total_courses"),
                        showcase=ui.span("Courses", style="font-size: 1.2rem; font-weight: bold; color: #3498db;"),
                        theme="primary"
                    ),
                    ui.value_box(
                        "Total Responses",
                        ui.output_text("total_responses"),
                        showcase=ui.span("Responses", style="font-size: 1.2rem; font-weight: bold; color: #2ecc71;"),
                        theme="success"
                    ),
                    ui.value_box(
                        "Avg Response Rate",
                        ui.output_text("avg_response_rate"),
                        showcase=ui.span("Rate", style="font-size: 1.2rem; font-weight: bold; color: #f39c12;"),
                        theme="warning"
                    ),
                    ui.value_box(
                        "Best Overall Score",
                        ui.output_text("best_score"),
                        showcase=ui.span("Best", style="font-size: 1.2rem; font-weight: bold; color: #e74c3c;"),
                        theme="danger"
                    ),
                    col_widths=[3, 3, 3, 3]
                ),
                style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
            ),
            col_widths=[12]
        ),
        ui.layout_columns(
            ui.card(
                ui.card_header("Score Distribution by Question"),
                output_widget("score_distribution", height="450px"),
                ui.card_footer(
                    ui.p(
                        "Lower scores indicate better performance (1 = Best, 5 = Worst). Hover over bars for exact values.",
                        class_="text-muted small mb-0")
                ),
                style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
            ),
            ui.card(
                ui.card_header("Performance Trends"),
                output_widget("performance_trends", height="450px"),
                ui.card_footer(
                    ui.p(
                        "Shows average quality scores and response rates over time. The shaded area represents standard deviation.",
                        class_="text-muted small mb-0")
                ),
                style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
            ),
            col_widths=[6, 6]
        ),
        ui.layout_columns(
            ui.card(
                ui.card_header("Top Performers (10+ Responses)"),
                ui.output_ui("top_performers"),
                ui.card_footer(
                    ui.p(
                        "Courses with the lowest (best) overall quality scores. Only includes courses with 10+ responses.",
                        class_="text-muted small mb-0")
                ),
                style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); max-height: 500px; overflow-y: auto;"
            ),
            ui.card(
                ui.card_header("Worst Performing Courses (10+ Responses)"),
                ui.output_ui("worst_performers"),
                ui.card_footer(
                    ui.p(
                        "Courses with the highest (worst) overall quality scores. Only includes courses with 10+ responses.",
                        class_="text-muted small mb-0")
                ),
                style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); max-height: 500px; overflow-y: auto;"
            ),
            col_widths=[6, 6]
        )
    ),

    ui.nav_panel(
        "Course Analysis",
        ui.layout_sidebar(
            create_filter_sidebar(),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Course Selection"),
                    ui.input_select(
                        "course_select",
                        "Select Course:",
                        choices={},
                        width="100%"
                    ),
                    ui.output_ui("course_quick_stats"),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                col_widths=[12]
            ),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Performance Radar"),
                    output_widget("course_radar", height="400px"),
                    ui.card_footer(
                        ui.p("Shows all feedback dimensions. Points closer to center indicate better performance.",
                             class_="text-muted small mb-0")
                    ),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                ui.card(
                    ui.card_header("Historical Trend"),
                    output_widget("course_history", height="400px"),
                    ui.card_footer(
                        ui.p(
                            "Lines show score trends (lower is better). Bars show response rate. Dashed line is overall trend.",
                            class_="text-muted small mb-0")
                    ),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                col_widths=[6, 6]
            ),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Detailed Metrics"),
                    output_widget("course_metrics", height="350px"),
                    ui.card_footer(
                        ui.p("Compares course scores to department average. Pie chart shows response rate breakdown.",
                             class_="text-muted small mb-0")
                    ),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                col_widths=[12]
            )
        )
    ),

    ui.nav_panel(
        "Comparisons",
        ui.layout_sidebar(
            create_filter_sidebar(),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Course Comparison Tool"),
                    ui.input_select(
                        "compare_courses",
                        "Select up to 5 courses:",
                        choices={},
                        multiple=True
                    ),
                    ui.input_radio_buttons(
                        "comparison_view",
                        "View Type:",
                        choices={
                            "Side by Side": "Side by Side - Individual charts for each course",
                            "Overlay": "Overlay - All courses on one chart",
                            "Difference": "Difference - Compare exactly 2 courses"
                        },
                        selected="Side by Side",
                        inline=False
                    ),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                col_widths=[12]
            ),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Comparison Visualization"),
                    output_widget("comparison_viz", height="500px"),
                    ui.card_footer(
                        ui.p(
                            "Remember: Lower scores are better (1 = Best, 5 = Worst) except for Q5 Workload where 3 is ideal.",
                            class_="text-muted small mb-0")
                    ),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                col_widths=[12]
            )
        )
    ),

    ui.nav_panel(
        "Department View",
        ui.layout_sidebar(
            create_filter_sidebar(),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Department Analysis"),
                    ui.input_select(
                        "dept_select",
                        "Select Department:",
                        choices=course_letters,
                        selected=course_letters[0] if course_letters else None
                    ),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                col_widths=[12]
            ),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Department Overview"),
                    output_widget("dept_heatmap", height="500px"),
                    ui.card_footer(
                        ui.p(
                            "Heatmap shows all courses (columns) and questions (rows). Green = Good (low scores), Red = Poor (high scores).",
                            class_="text-muted small mb-0")
                    ),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                ui.card(
                    ui.card_header("Department Statistics"),
                    ui.output_ui("dept_summary"),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                col_widths=[8, 4]
            )
        )
    ),

    ui.nav_panel(
        "Data Explorer",
        ui.layout_sidebar(
            create_filter_sidebar(),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Data Explorer"),
                    ui.layout_columns(
                        ui.input_text("search_box", "Search:",
                                      placeholder="Filter by course code, title, or department..."),
                        col_widths=[12]
                    ),
                    ui.hr(),
                    ui.output_data_frame("data_explorer"),
                    ui.card_footer(
                        ui.p(
                            "All columns are displayed except rank columns. Use filters and search to find specific courses.",
                            class_="text-muted small mb-0")
                    ),
                    style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
                ),
                col_widths=[12]
            )
        )
    ),

    ui.nav_panel(
        "About",
        ui.layout_columns(
            ui.card(
                ui.card_header("About This Dashboard"),
                ui.output_ui("about_content"),
                style="box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);"
            ),
            col_widths=[12]
        )
    ),

    title="Victoria University of Wellington Course Feedback Analytics",
    navbar_options=ui.navbar_options(
        bg="#2c3e50"
    ),
    header=ui.tags.style("""
        /* Modern styling */
        .navbar {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%) !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .navbar .navbar-brand, .navbar .nav-link {
            color: white !important;
            font-weight: 500;
        }
        .navbar .nav-link:hover {
            background-color: rgba(255,255,255,0.1);
            border-radius: 5px;
        }
        .navbar .nav-link.active {
            background-color: rgba(255,255,255,0.2) !important;
            border-radius: 5px;
        }
        .card {
            border: none;
            border-radius: 10px;
            transition: transform 0.2s;
        }
        .card:hover {
            transform: translateY(-2px);
        }
        .card-header {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-bottom: 2px solid #e9ecef;
            font-weight: 600;
            font-size: 1.1rem;
        }
        .card-footer {
            background-color: #f8f9fa;
            border-top: 1px solid #e9ecef;
        }
        .value-box {
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }
        .value-box:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.15);
        }
        /* Table styling */
        .styled-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95rem;
        }
        .styled-table thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .styled-table th {
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
        }
        .styled-table td {
            padding: 10px 15px;
            border-bottom: 1px solid #e0e0e0;
        }
        .styled-table tbody tr:hover {
            background-color: #f5f5f5;
            cursor: pointer;
        }
        .styled-table tbody tr:nth-child(even) {
            background-color: #f9f9f9;
        }
    """)
)


def server(input: Inputs, output: Outputs, session: Session):
    # Reactive calculations
    @reactive.calc
    def filtered_data():
        df = feedback_df.copy()

        # Apply filters
        if "All" not in input.year_filter() and input.year_filter():
            df = df[df['Year'].isin([int(y) for y in input.year_filter()])]

        if "All" not in input.dept_filter() and input.dept_filter():
            df = df[df['Course Letter'].isin(input.dept_filter())]

        df = df[df['Responses'] >= input.response_filter()]

        if input.exclude_low_sample():
            df = df[df['Low Sample'] == False]

        return df

    @reactive.effect
    def update_course_selections():
        df = filtered_data()
        courses = df['Course Full'].unique()
        course_dict = {course: course for course in sorted(courses)}
        ui.update_select("course_select", choices=course_dict)
        ui.update_select("compare_courses", choices=course_dict)

    # Overview outputs
    @render.text
    def total_courses():
        return f"{feedback_df['Course Code'].nunique():,}"

    @render.text
    def total_responses():
        return f"{feedback_df['Responses'].sum():,}"

    @render.text
    def avg_response_rate():
        rate = feedback_df['Response Rate'].mean()
        return f"{rate:.1f}%"

    @render.text
    def best_score():
        best = feedback_df['Q9: Overall quality'].min()
        return f"{best:.2f}"

    @render_plotly
    def score_distribution():
        # Calculate average scores
        q_cols = [col for col in feedback_df.columns if col.startswith('Q') and 'Rank' not in col]
        avg_scores = feedback_df[q_cols].mean().sort_values()

        # Create interactive bar chart
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=avg_scores.values,
            y=[QUESTION_SHORT.get(q, q) for q in avg_scores.index],
            orientation='h',
            marker=dict(
                color=avg_scores.values,
                colorscale='RdYlGn_r',
                cmin=1,
                cmax=5,
                showscale=True,
                colorbar=dict(title="Score")
            ),
            text=[f'{v:.2f}' for v in avg_scores.values],
            textposition='outside',
            hovertemplate='%{y}: %{x:.2f}<extra></extra>'
        ))

        fig.update_layout(
            title="Average Scores by Question (Lower is Better)",
            xaxis_title="Average Score",
            yaxis_title="",
            height=450,
            xaxis=dict(range=[0, 5]),
            showlegend=False,
            margin=dict(l=150)
        )

        return fig

    @render_plotly
    def performance_trends():
        # Create subplots
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Quality Trends Over Time", "Response Rate Trends"),
            vertical_spacing=0.15,
            shared_xaxes=True
        )

        # Trend 1: Average quality over years
        yearly_quality = feedback_df.groupby('Year')['Q9: Overall quality'].agg(['mean', 'std']).reset_index()

        # Add mean line
        fig.add_trace(
            go.Scatter(
                x=yearly_quality['Year'],
                y=yearly_quality['mean'],
                mode='lines+markers',
                name='Avg Quality',
                line=dict(color=COLORS['primary'], width=3),
                marker=dict(size=10),
                hovertemplate='Year: %{x}<br>Avg Quality: %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # Add confidence interval
        fig.add_trace(
            go.Scatter(
                x=yearly_quality['Year'].tolist() + yearly_quality['Year'].tolist()[::-1],
                y=(yearly_quality['mean'] - yearly_quality['std']).tolist() +
                  (yearly_quality['mean'] + yearly_quality['std']).tolist()[::-1],
                fill='toself',
                fillcolor='rgba(52, 152, 219, 0.2)',
                line=dict(color='rgba(255,255,255,0)'),
                showlegend=False,
                hoverinfo='skip'
            ),
            row=1, col=1
        )

        # Trend 2: Response rates
        yearly_response = feedback_df.groupby('Year').agg({
            'Responses': 'sum',
            'Enrolled': 'sum'
        }).reset_index()
        yearly_response['Rate'] = (yearly_response['Responses'] / yearly_response['Enrolled'] * 100)

        fig.add_trace(
            go.Bar(
                x=yearly_response['Year'],
                y=yearly_response['Rate'],
                name='Response Rate',
                marker_color=COLORS['success'],
                opacity=0.7,
                hovertemplate='Year: %{x}<br>Response Rate: %{y:.1f}%<extra></extra>'
            ),
            row=2, col=1
        )

        fig.update_xaxes(title_text="Year", row=2, col=1)
        fig.update_yaxes(title_text="Avg Overall Quality", range=[1, 5], row=1, col=1)
        fig.update_yaxes(title_text="Response Rate (%)", row=2, col=1)

        fig.update_layout(
            height=450,
            showlegend=False,
            hovermode='x unified'
        )

        return fig

    @render.ui
    def top_performers():
        # Filter for courses with 10+ responses
        top = feedback_df[feedback_df['Responses'] >= 10].nsmallest(10, 'Q9: Overall quality')

        if len(top) == 0:
            return ui.HTML("<p class='text-center text-muted'>No courses with 10+ responses found</p>")

        html = """
        <table class="styled-table">
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Course</th>
                    <th>Year</th>
                    <th>Score</th>
                    <th>Responses</th>
                </tr>
            </thead>
            <tbody>
        """

        for i, (_, row) in enumerate(top.iterrows(), 1):
            html += f"""
                <tr>
                    <td><span style="background-color: #2ecc71; color: white; padding: 2px 8px; border-radius: 3px;">{i}</span></td>
                    <td><strong>{row['Course Code']}</strong><br><small>{row['Course Title'][:40]}...</small></td>
                    <td>{row['Year']}</td>
                    <td><strong style="color: #27ae60;">{row['Q9: Overall quality']:.2f}</strong></td>
                    <td>{row['Responses']}</td>
                </tr>
            """

        html += "</tbody></table>"
        return ui.HTML(html)

    @render.ui
    def worst_performers():
        # Filter for courses with 10+ responses
        bottom = feedback_df[feedback_df['Responses'] >= 10].nlargest(10, 'Q9: Overall quality')

        if len(bottom) == 0:
            return ui.HTML("<p class='text-center text-muted'>No courses with 10+ responses found</p>")

        html = """
        <table class="styled-table">
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Course</th>
                    <th>Year</th>
                    <th>Score</th>
                    <th>Responses</th>
                </tr>
            </thead>
            <tbody>
        """

        for i, (_, row) in enumerate(bottom.iterrows(), 1):
            html += f"""
                <tr>
                    <td><span style="background-color: #e74c3c; color: white; padding: 2px 8px; border-radius: 3px;">{i}</span></td>
                    <td><strong>{row['Course Code']}</strong><br><small>{row['Course Title'][:40]}...</small></td>
                    <td>{row['Year']}</td>
                    <td><strong style="color: #c0392b;">{row['Q9: Overall quality']:.2f}</strong></td>
                    <td>{row['Responses']}</td>
                </tr>
            """

        html += "</tbody></table>"
        return ui.HTML(html)

    # Course Analysis outputs
    @render.ui
    def course_quick_stats():
        if not input.course_select():
            return ui.div()

        course_code = input.course_select().split(' - ')[0]
        course_data = feedback_df[feedback_df['Course Code'] == course_code]
        latest = course_data.iloc[-1]

        return ui.div(
            ui.hr(),
            ui.h5("Quick Stats", class_="text-center"),
            ui.div(
                ui.div(
                    ui.strong("Overall Score: "),
                    ui.span(f"{latest['Q9: Overall quality']:.2f}",
                            style=f"color: {'green' if latest['Q9: Overall quality'] < 3 else 'red'}")
                ),
                ui.div(
                    ui.strong("Response Rate: "),
                    ui.span(f"{latest['Response Rate']:.1f}%")
                ),
                ui.div(
                    ui.strong("Years Offered: "),
                    ui.span(str(len(course_data)))
                ),
                style="background-color: white; padding: 15px; border-radius: 5px; margin-top: 10px;"
            )
        )

    @render_plotly
    def course_radar():
        if not input.course_select():
            fig = go.Figure()
            fig.add_annotation(
                text="Select a course to view analysis",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=400
            )
            return fig

        course_code = input.course_select().split(' - ')[0]
        course_data = feedback_df[feedback_df['Course Code'] == course_code].iloc[-1]

        # Prepare radar data
        categories = ['Q1', 'Q2', 'Q3', 'Q4', 'Q6', 'Q7', 'Q8', 'Q9']
        values = []

        for cat in categories:
            for col in feedback_df.columns:
                if col.startswith(cat + ':'):
                    values.append(course_data[col])
                    break

        # Create radar chart
        fig = go.Figure()

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=[QUESTION_SHORT.get(f"{cat}: ", cat) for cat in categories],
            fill='toself',
            name=course_code,
            line_color=COLORS['primary'],
            fillcolor='rgba(52, 152, 219, 0.3)',
            hovertemplate='%{theta}: %{r:.2f}<extra></extra>'
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[1, 5]
                )
            ),
            showlegend=True,
            title=f"Performance Profile: {course_code}",
            height=400
        )

        return fig

    @render_plotly
    def course_history():
        if not input.course_select():
            fig = go.Figure()
            fig.add_annotation(
                text="Select a course to view history",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=400
            )
            return fig

        course_code = input.course_select().split(' - ')[0]
        history = feedback_df[feedback_df['Course Code'] == course_code].sort_values('Year')

        if len(history) < 2:
            fig = go.Figure()
            fig.add_annotation(
                text="Insufficient historical data",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=400
            )
            return fig

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Quality metrics over time
        metrics = ['Q1: Well-organised', 'Q2: Clear communication', 'Q9: Overall quality']
        colors = [COLORS['primary'], COLORS['success'], COLORS['danger']]

        for metric, color in zip(metrics, colors):
            fig.add_trace(
                go.Scatter(
                    x=history['Year'],
                    y=history[metric],
                    mode='lines+markers',
                    name=QUESTION_SHORT.get(metric, metric),
                    line=dict(color=color, width=2.5),
                    marker=dict(size=8),
                    hovertemplate='Year: %{x}<br>' + QUESTION_SHORT.get(metric, metric) + ': %{y:.2f}<extra></extra>'
                ),
                secondary_y=False
            )

        # Response rate bars
        fig.add_trace(
            go.Bar(
                x=history['Year'],
                y=history['Response Rate'],
                name='Response Rate %',
                marker_color=COLORS['info'],
                opacity=0.3,
                yaxis='y2',
                hovertemplate='Year: %{x}<br>Response Rate: %{y:.1f}%<extra></extra>'
            ),
            secondary_y=True
        )

        # Add trend line
        z = np.polyfit(history['Year'], history['Q9: Overall quality'], 1)
        p = np.poly1d(z)
        fig.add_trace(
            go.Scatter(
                x=history['Year'],
                y=p(history['Year']),
                mode='lines',
                name='Trend',
                line=dict(color='gray', dash='dash'),
                hoverinfo='skip'
            ),
            secondary_y=False
        )

        fig.update_xaxes(title_text="Year")
        fig.update_yaxes(title_text="Score (Lower is Better)", secondary_y=False, range=[1, 5])
        fig.update_yaxes(title_text="Response Rate (%)", secondary_y=True)

        fig.update_layout(
            title=f"Historical Performance: {course_code}",
            height=400,
            hovermode='x unified'
        )

        return fig

    @render_plotly
    def course_metrics():
        if not input.course_select():
            return go.Figure()

        course_code = input.course_select().split(' - ')[0]
        course_data = feedback_df[feedback_df['Course Code'] == course_code].iloc[-1]

        # Create subplots
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Course vs Department Average", f"Response Rate: {course_data['Response Rate']:.1f}%"),
            specs=[[{"type": "bar"}, {"type": "pie"}]]
        )

        # Metric comparison
        metrics = ['Q1: Well-organised', 'Q2: Clear communication',
                   'Q3: Assessment helped', 'Q4: Helpful feedback',
                   'Q6: Understanding', 'Q7: Interest',
                   'Q8: Valuable', 'Q9: Overall quality']

        values = [course_data[m] for m in metrics]
        dept_avg = feedback_df[feedback_df['Course Letter'] == course_data['Course Letter']][metrics].mean()

        # Bar chart
        fig.add_trace(
            go.Bar(
                x=[QUESTION_SHORT.get(m, m) for m in metrics],
                y=values,
                name='Course',
                marker_color=COLORS['primary'],
                hovertemplate='%{x}: %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        fig.add_trace(
            go.Bar(
                x=[QUESTION_SHORT.get(m, m) for m in metrics],
                y=dept_avg,
                name='Dept Avg',
                marker_color=COLORS['warning'],
                opacity=0.7,
                hovertemplate='%{x}: %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # Pie chart
        labels = ['Responded', 'Did Not Respond']
        sizes = [course_data['Responses'], course_data['Enrolled'] - course_data['Responses']]

        fig.add_trace(
            go.Pie(
                labels=labels,
                values=sizes,
                hole=0.3,
                marker_colors=[COLORS['success'], COLORS['light']],
                textposition='auto',
                textinfo='percent+label',
                hovertemplate='%{label}: %{value} (%{percent})<extra></extra>'
            ),
            row=1, col=2
        )

        fig.update_xaxes(tickangle=-45, row=1, col=1)
        fig.update_yaxes(range=[0, 5], row=1, col=1)

        fig.update_layout(
            height=350,
            showlegend=True,
            margin=dict(b=100)
        )

        return fig

    # Comparison outputs
    @render_plotly
    def comparison_viz():
        if not input.compare_courses() or len(input.compare_courses()) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="Select courses to compare",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="gray")
            )
            fig.update_layout(
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=500
            )
            return fig

        selected = input.compare_courses()[:5]
        view_type = input.comparison_view()

        if view_type == "Side by Side":
            # Create subplots
            fig = make_subplots(
                rows=1, cols=len(selected),
                subplot_titles=[c.split(' - ')[0] for c in selected]
            )

            for i, course in enumerate(selected):
                course_code = course.split(' - ')[0]
                data = feedback_df[feedback_df['Course Code'] == course_code].iloc[-1]

                metrics = ['Q1', 'Q2', 'Q3', 'Q4', 'Q6', 'Q7', 'Q8', 'Q9']
                values = []
                for m in metrics:
                    for col in feedback_df.columns:
                        if col.startswith(m + ':'):
                            values.append(data[col])
                            break

                fig.add_trace(
                    go.Bar(
                        x=metrics,
                        y=values,
                        name=course_code,
                        marker_color=COLORS['gradient'][i % len(COLORS['gradient'])],
                        showlegend=False,
                        hovertemplate='%{x}: %{y:.2f}<extra></extra>'
                    ),
                    row=1, col=i + 1
                )

                fig.update_yaxes(range=[0, 5], row=1, col=i + 1)

        elif view_type == "Overlay":
            fig = go.Figure()

            metrics = ['Q1: Well-organised', 'Q2: Clear communication',
                       'Q3: Assessment helped', 'Q4: Helpful feedback',
                       'Q6: Understanding', 'Q7: Interest',
                       'Q8: Valuable', 'Q9: Overall quality']

            for i, course in enumerate(selected):
                course_code = course.split(' - ')[0]
                data = feedback_df[feedback_df['Course Code'] == course_code].iloc[-1]
                values = [data[m] for m in metrics]

                fig.add_trace(go.Bar(
                    x=[QUESTION_SHORT.get(m, m) for m in metrics],
                    y=values,
                    name=course_code,
                    marker_color=COLORS['gradient'][i % len(COLORS['gradient'])],
                    opacity=0.8,
                    hovertemplate='%{x}: %{y:.2f}<extra></extra>'
                ))

            fig.update_layout(
                barmode='group',
                xaxis_tickangle=-45,
                yaxis=dict(range=[0, 5], title="Score"),
                xaxis_title="Questions"
            )

        else:  # Difference
            if len(selected) != 2:
                fig = go.Figure()
                fig.add_annotation(
                    text="Select exactly 2 courses for difference view",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16, color="gray")
                )
                fig.update_layout(
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False),
                    height=500
                )
                return fig

            fig = go.Figure()

            metrics = ['Q1: Well-organised', 'Q2: Clear communication',
                       'Q3: Assessment helped', 'Q4: Helpful feedback',
                       'Q6: Understanding', 'Q7: Interest',
                       'Q8: Valuable', 'Q9: Overall quality']

            course1_code = selected[0].split(' - ')[0]
            course2_code = selected[1].split(' - ')[0]

            data1 = feedback_df[feedback_df['Course Code'] == course1_code].iloc[-1]
            data2 = feedback_df[feedback_df['Course Code'] == course2_code].iloc[-1]

            differences = [data2[m] - data1[m] for m in metrics]
            colors = [COLORS['success'] if d < 0 else COLORS['danger'] for d in differences]

            fig.add_trace(go.Bar(
                x=[QUESTION_SHORT.get(m, m) for m in metrics],
                y=differences,
                marker_color=colors,
                text=[f'{d:+.2f}' for d in differences],
                textposition='outside',
                hovertemplate='%{x}: %{text}<extra></extra>'
            ))

            fig.add_hline(y=0, line_color="black", line_width=1)

            fig.update_layout(
                title=f"Performance Difference: {course2_code} vs {course1_code}",
                xaxis_title="Questions",
                yaxis_title=f"Difference ({course2_code} - {course1_code})",
                xaxis_tickangle=-45,
                showlegend=False
            )

        fig.update_layout(
            height=500,
            margin=dict(b=100)
        )

        return fig

    # Department outputs
    @render_plotly
    def dept_heatmap():
        if not input.dept_select():
            return go.Figure()

        dept = input.dept_select()
        dept_data = feedback_df[feedback_df['Course Letter'] == dept]

        # Create course x metric matrix
        courses = dept_data.groupby('Course Code').last()
        metrics = ['Q1: Well-organised', 'Q2: Clear communication',
                   'Q3: Assessment helped', 'Q4: Helpful feedback',
                   'Q6: Understanding', 'Q7: Interest',
                   'Q8: Valuable', 'Q9: Overall quality']

        matrix = courses[metrics].values.T

        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=matrix,
            x=courses.index,
            y=[QUESTION_SHORT.get(m, m) for m in metrics],
            colorscale='RdYlGn_r',
            zmin=1,
            zmax=5,
            text=[[f'{val:.1f}' for val in row] for row in matrix],
            texttemplate='%{text}',
            textfont={"size": 10},
            hovertemplate='Course: %{x}<br>Question: %{y}<br>Score: %{z:.2f}<extra></extra>'
        ))

        fig.update_layout(
            title=f"Department {dept} - Course Performance Heatmap",
            xaxis_title="Course Code",
            yaxis_title="Questions",
            height=500,
            xaxis={'side': 'bottom'},
            margin=dict(l=100)
        )

        return fig

    @render.ui
    def dept_summary():
        if not input.dept_select():
            return ui.div()

        dept = input.dept_select()
        dept_data = feedback_df[feedback_df['Course Letter'] == dept]

        # Calculate statistics
        total_courses = dept_data['Course Code'].nunique()
        total_responses = dept_data['Responses'].sum()
        avg_enrollment = dept_data['Enrolled'].mean()
        avg_quality = dept_data['Q9: Overall quality'].mean()
        avg_response_rate = dept_data['Response Rate'].mean()

        # Get best and worst courses
        best_courses = dept_data.nsmallest(5, 'Q9: Overall quality')['Course Code'].tolist()
        worst_courses = dept_data.nlargest(5, 'Q9: Overall quality')['Course Code'].tolist()

        html = f"""
        <div style="padding: 20px;">
            <h4>Department {dept} Statistics</h4>
            <hr>
            <div style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <strong>Total Unique Courses:</strong> <span>{total_courses}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <strong>Total Responses:</strong> <span>{total_responses:,}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <strong>Average Enrollment:</strong> <span>{avg_enrollment:.1f}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <strong>Average Overall Quality:</strong> 
                    <span style="color: {'green' if avg_quality < 3 else 'red'}; font-weight: bold;">
                        {avg_quality:.2f}
                    </span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <strong>Average Response Rate:</strong> <span>{avg_response_rate:.1f}%</span>
                </div>
            </div>
            <hr>
            <div style="margin-top: 20px;">
                <h5>Top Performing Courses</h5>
                <p>{', '.join(best_courses)}</p>
            </div>
            <div style="margin-top: 20px;">
                <h5>Worst Performing Courses</h5>
                <p>{', '.join(worst_courses)}</p>
            </div>
        </div>
        """

        return ui.HTML(html)

    # Data Explorer output
    @render.data_frame
    def data_explorer():
        df = filtered_data()

        # Apply search filter
        if input.search_box():
            search = input.search_box().lower()
            df = df[
                df['Course Code'].str.lower().str.contains(search) |
                df['Course Title'].str.lower().str.contains(search) |
                df['Course Letter'].str.lower().str.contains(search)
                ]

        # Select display columns (exclude rank columns which were already removed)
        display_cols = [col for col in df.columns if col != 'Course Full']

        return render.DataGrid(
            df[display_cols],
            width="100%",
            height="600px",
            filters=True
        )

    # About page content
    @render.ui
    def about_content():
        html = """
        <div style="padding: 40px; max-width: 800px; margin: 0 auto;">
            <h2>Victoria University of Wellington Course Feedback Analytics Dashboard</h2>
            <p class="lead">This dashboard provides comprehensive analysis of student course feedback data at Victoria University of Wellington.</p>

            <hr>

            <h3>Understanding the Scoring System</h3>
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h5>Important: Lower Scores are Better!</h5>
                <ul>
                    <li><strong>1 = Excellent/Strongly Agree</strong> (Best possible score)</li>
                    <li><strong>2 = Good/Agree</strong></li>
                    <li><strong>3 = Neutral</strong></li>
                    <li><strong>4 = Poor/Disagree</strong></li>
                    <li><strong>5 = Very Poor/Strongly Disagree</strong> (Worst possible score)</li>
                </ul>
                <p><em>Exception: For Q5 (Workload), 3 is ideal, with 1 being "too much work" and 5 being "too little work".</em></p>
            </div>

            <h3>Survey Questions</h3>
            <ol>
                <li><strong>Q1: Organisation</strong> - Was the course well-organised?</li>
                <li><strong>Q2: Communication</strong> - Was important course information communicated clearly?</li>
                <li><strong>Q3: Assessment</strong> - Did assessment tasks help learning?</li>
                <li><strong>Q4: Feedback</strong> - Did you receive helpful feedback on progress?</li>
                <li><strong>Q5: Workload</strong> - Was the amount of work appropriate? (3 = ideal)</li>
                <li><strong>Q6: Understanding</strong> - Did the course help develop understanding?</li>
                <li><strong>Q7: Interest</strong> - Did the course stimulate interest in the subject?</li>
                <li><strong>Q8: Value</strong> - Was what you learned valuable?</li>
                <li><strong>Q9: Overall Quality</strong> - How would you rate the overall quality?</li>
            </ol>

            <h3>Using the Dashboard</h3>
            <ul>
                <li><strong>Filters:</strong> Available on all pages except Overview. Changes apply across all pages.</li>
                <li><strong>Interactive Charts:</strong> Click and drag to zoom, double-click to reset. Hover for details.</li>
                <li><strong>Color Coding:</strong> Green indicates good performance, red indicates areas for improvement.</li>
                <li><strong>Response Threshold:</strong> Top/Worst performers only show courses with 10+ responses for statistical validity.</li>
            </ul>

            <h3>Data Notes</h3>
            <ul>
                <li>Data includes courses from 2007 to the most recent completed trimester</li>
                <li>Student feedback is collected at least once every three offerings of a course</li>
                <li>Low sample courses are flagged when response counts may not be statistically significant</li>
                <li>Department averages provide context for individual course performance</li>
            </ul>

            <hr>

            <h3>Disclaimer</h3>
            <p>This dashboard is an unofficial tool created for exploration and insight into course feedback data. While the data is drawn from official VUW sources, it may contain inaccuracies or gaps and should not be used for formal reporting or decision-making. Interpret results with care, especially where response numbers are low. For official analysis, please refer to VUW.</p>

            <div style="margin-top: 40px; padding: 20px; background-color: #e9ecef; border-radius: 5px;">
                <h5>Custom Content Area</h5>
                <p>This section can be customized with institution-specific information, contact details, or additional notes.</p>
                <!-- Add your custom HTML content here -->
            </div>
        </div>
        """

        return ui.HTML(html)


# Create the app
app = App(app_ui, server)

# If run directly
if __name__ == "__main__":
    print("=" * 60)
    print("Course Feedback Dashboard - Enhanced Plotly Version")
    print("=" * 60)
    print("This app should be run using the Shiny command.")
    print()
    print("To start the dashboard, use:")
    print("  shiny run app.py --reload")
    print()
    print("Or use the launcher:")
    print("  python run.py")
    print("=" * 60)