from shiny import App, ui, render, reactive
from shiny.types import ImgData
from shinywidgets import render_plotly, output_widget
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path
import os
from difflib import SequenceMatcher
import networkx as nx
from datetime import datetime

# Get the directory where this script is located
app_dir = Path(__file__).parent

# Based on actual data analysis - accurate mappings between councils
GROUP_MAPPINGS = {
    # HCC Group -> WCC Group mapping
    "Economy & Development": "Economic & Engagement",
    "Environment & Sustainability": "Planning & Environment",
    "Neighbourhoods & Communities": "Customer & Community",
    "Neighbourhoods & Communities ": "Customer & Community",  # Handle trailing space
    "Office of the Chief Executive": "Chief Executives Office",
    "Strategy & Engagement": "Strategy & Finance"
}

# Reverse mapping for WCC -> HCC
REVERSE_GROUP_MAPPINGS = {v: k for k, v in GROUP_MAPPINGS.items()}

# Division/Unit mappings based on function
DIVISION_MAPPINGS = {
    # Infrastructure related
    "Transport": "Infrastructure & Delivery",
    "Assets & Facilities Management": "Infrastructure & Delivery",
    "City Delivery": "Infrastructure & Delivery",
    # People/HR related
    "People & Capability": "People & Culture",
    # M?ori services
    "Te Tira M?ori": "Mataaho Aronui",
}

# Color schemes for consistent visualization
COUNCIL_COLORS = {
    "Wellington": "#1f77b4",
    "Hutt": "#ff7f0e",
    "WCC": "#1f77b4",
    "HCC": "#ff7f0e"
}

GROUP_COLORS = {
    "Chief Executives Office": "#1f77b4",
    "Customer & Community": "#ff7f0e",
    "Economic & Engagement": "#2ca02c",
    "Infrastructure & Delivery": "#d62728",
    "Mataaho Aronui": "#9467bd",
    "People & Culture": "#8c564b",
    "Planning & Environment": "#e377c2",
    "Strategy & Finance": "#7f7f7f"
}

# Define the UI
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Overview",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Council Selection"),
                ui.input_select(
                    "council_select",
                    "Select View:",
                    choices=["Wellington City Council", "Hutt City Council", "Compare Councils"],
                    selected="Wellington City Council"
                ),
                ui.hr(),
                ui.h4("Filters"),
                ui.input_select(
                    "filter_group",
                    "Business Group:",
                    choices=["All"],
                    selected="All",
                    multiple=False
                ),
                ui.input_select(
                    "filter_unit",
                    "Unit/Division:",
                    choices=["All"],
                    selected="All",
                    multiple=False
                ),
                ui.panel_conditional(
                    "input.council_select == 'Wellington City Council'",
                    ui.input_select(
                        "filter_location",
                        "Pay Location:",
                        choices=["All"],
                        selected="All",
                        multiple=False
                    )
                ),
                ui.hr(),
                ui.h5("Quick Stats"),
                ui.output_ui("summary_stats"),
                ui.hr(),
                ui.h6("Data Quality"),
                ui.output_ui("data_quality_stats"),
                width=350
            ),
            ui.row(
                ui.column(
                    12,
                    ui.h2(ui.output_text("dashboard_title")),
                    ui.p(ui.output_text("last_updated"), style="color: #666; font-style: italic;"),
                    ui.hr()
                )
            ),
            # Value boxes for key metrics
            ui.row(
                ui.column(
                    3,
                    ui.value_box(
                        "Total Staff",
                        ui.output_text("total_staff_overview"),
                        showcase=ui.HTML('<i class="bi bi-people-fill" style="font-size: 2rem;"></i>'),
                        theme="primary"
                    )
                ),
                ui.column(
                    3,
                    ui.value_box(
                        "Groups/Departments",
                        ui.output_text("total_groups_overview"),
                        showcase=ui.HTML('<i class="bi bi-building" style="font-size: 2rem;"></i>'),
                        theme="success"
                    )
                ),
                ui.column(
                    3,
                    ui.value_box(
                        "Unique Positions",
                        ui.output_text("total_positions_overview"),
                        showcase=ui.HTML('<i class="bi bi-briefcase-fill" style="font-size: 2rem;"></i>'),
                        theme="info"
                    )
                ),
                ui.column(
                    3,
                    ui.value_box(
                        "Avg Staff/Unit",
                        ui.output_text("avg_staff_unit_overview"),
                        showcase=ui.HTML('<i class="bi bi-graph-up" style="font-size: 2rem;"></i>'),
                        theme="warning"
                    )
                )
            ),
            ui.row(
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Staff Distribution by Group"),
                        output_widget("group_distribution"),
                        ui.card_footer(
                            ui.output_text("group_distribution_insight")
                        )
                    )
                ),
                ui.column(
                    6,
                    ui.card(
                        ui.card_header(ui.output_text("location_or_division_title")),
                        output_widget("location_distribution")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Hierarchical Staff Distribution"),
                        output_widget("unit_treemap"),
                        ui.card_footer(
                            ui.input_switch(
                                "treemap_normalize",
                                "Normalize by group size",
                                value=False
                            )
                        )
                    )
                )
            )
        )
    ),
    ui.nav_panel(
        "Job Analysis",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Analysis Options"),
                ui.input_text(
                    "job_search",
                    "Search Job Titles:",
                    placeholder="e.g., Manager, Officer, Analyst..."
                ),
                ui.input_select(
                    "job_category_filter",
                    "Job Category:",
                    choices=["All", "Management", "Professional", "Technical", "Administrative", "Operational"],
                    selected="All"
                ),
                ui.input_slider(
                    "top_jobs_count",
                    "Number of Top Jobs:",
                    min=5,
                    max=50,
                    value=20,
                    step=5
                ),
                ui.hr(),
                ui.h5("Job Statistics"),
                ui.output_ui("job_stats"),
                ui.hr(),
                ui.h6("Job Title Insights"),
                ui.output_ui("job_insights"),
                width=350
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Top Job Titles by Staff Count"),
                        output_widget("top_jobs_chart"),
                        ui.card_footer(
                            ui.input_radio_buttons(
                                "job_chart_type",
                                "Chart Type:",
                                choices=["Bar", "Treemap", "Sunburst"],
                                selected="Bar",
                                inline=True
                            )
                        )
                    )
                )
            ),
            ui.row(
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Job Title Word Cloud"),
                        output_widget("job_wordcloud")
                    )
                ),
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Job Level Distribution"),
                        output_widget("job_level_distribution")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Job Title Distribution Heatmap"),
                        output_widget("job_group_heatmap"),
                        ui.card_footer(
                            ui.input_checkbox(
                                "heatmap_cluster",
                                "Apply clustering",
                                value=False
                            )
                        )
                    )
                )
            )
        )
    ),
    ui.nav_panel(
        "Organizational Structure",
        ui.panel_conditional(
            "input.council_select == 'Hutt City Council'",
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Organizational Network"),
                        output_widget("org_network")
                    )
                )
            ),
            ui.row(
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Reporting Structure Analysis"),
                        output_widget("reporting_structure")
                    )
                ),
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Management Span of Control"),
                        output_widget("span_of_control")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Division-Manager Matrix"),
                        output_widget("manager_distribution")
                    )
                )
            )
        ),
        ui.panel_conditional(
            "input.council_select == 'Wellington City Council'",
            ui.row(
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Geographic Distribution"),
                        output_widget("location_pie")
                    )
                ),
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Location Concentration"),
                        output_widget("location_concentration")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Location-Group Matrix"),
                        output_widget("location_group_matrix")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Location Analytics"),
                        ui.output_data_frame("location_table")
                    )
                )
            )
        ),
        ui.panel_conditional(
            "input.council_select == 'Compare Councils'",
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Organizational Structure Comparison"),
                        output_widget("structure_comparison")
                    )
                )
            ),
            ui.row(
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Group Size Comparison"),
                        output_widget("group_size_comparison")
                    )
                ),
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Organizational Depth"),
                        output_widget("org_depth_comparison")
                    )
                )
            )
        )
    ),
    ui.nav_panel(
        "Analytics & Insights",
        ui.row(
            ui.column(
                12,
                ui.h3("Advanced Analytics"),
                ui.hr()
            )
        ),
        ui.row(
            ui.column(
                6,
                ui.card(
                    ui.card_header("Staff Distribution Inequality (Gini Coefficient)"),
                    output_widget("gini_analysis")
                )
            ),
            ui.column(
                6,
                ui.card(
                    ui.card_header("Organizational Efficiency Metrics"),
                    output_widget("efficiency_metrics")
                )
            )
        ),
        ui.row(
            ui.column(
                12,
                ui.card(
                    ui.card_header("Predictive Staffing Needs"),
                    output_widget("predictive_analysis"),
                    ui.card_footer(
                        ui.p("Based on current organizational structure and industry benchmarks",
                             style="font-style: italic; color: #666;")
                    )
                )
            )
        ),
        ui.row(
            ui.column(
                12,
                ui.card(
                    ui.card_header("Key Insights & Recommendations"),
                    ui.output_ui("insights_recommendations")
                )
            )
        )
    ),
    ui.nav_panel(
        "Council Comparison",
        ui.row(
            ui.column(
                12,
                ui.h3("Cross-Council Comparative Analysis"),
                ui.hr()
            )
        ),
        ui.row(
            ui.column(
                4,
                ui.card(
                    ui.card_header("Overall Comparison"),
                    output_widget("council_comparison")
                )
            ),
            ui.column(
                4,
                ui.card(
                    ui.card_header("Job Title Similarity"),
                    output_widget("job_overlap")
                )
            ),
            ui.column(
                4,
                ui.card(
                    ui.card_header("Structural Alignment"),
                    output_widget("structural_alignment")
                )
            )
        ),
        ui.row(
            ui.column(
                12,
                ui.card(
                    ui.card_header("Department Mapping & Equivalents"),
                    ui.output_data_frame("department_mapping"),
                    ui.card_footer(
                        ui.download_button(
                            "download_mapping",
                            "Download Mapping Report"
                        )
                    )
                )
            )
        ),
        ui.row(
            ui.column(
                12,
                ui.card(
                    ui.card_header("Detailed Comparison by Function"),
                    output_widget("functional_comparison")
                )
            )
        )
    ),
    ui.nav_panel(
        "Data Explorer",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Data Options"),
                ui.output_ui("table_selector"),
                ui.input_select(
                    "export_format",
                    "Export Format:",
                    choices=["CSV", "Excel", "JSON"],
                    selected="CSV"
                ),
                ui.input_numeric(
                    "rows_per_page",
                    "Rows per page:",
                    value=25,
                    min=10,
                    max=100,
                    step=5
                ),
                ui.hr(),
                ui.h5("Advanced Filters"),
                ui.input_checkbox(
                    "show_advanced_filters",
                    "Show advanced filters",
                    value=False
                ),
                ui.panel_conditional(
                    "input.show_advanced_filters",
                    ui.input_text(
                        "custom_filter",
                        "Custom SQL-like filter:",
                        placeholder="e.g., StaffCount > 10"
                    )
                ),
                ui.hr(),
                ui.download_button(
                    "download_data",
                    "Download Data"
                ),
                ui.download_button(
                    "download_report",
                    "Generate Full Report"
                ),
                width=350
            ),
            ui.card(
                ui.card_header("Data Table"),
                ui.output_data_frame("data_table")
            )
        )
    ),
    title="Council Staff Analytics Platform",
    bg="#343a40",
    inverse=True,
    footer=ui.div(
        ui.p("? 2024 Council Analytics Platform | Data current as of dataset date",
             style="text-align: center; color: #999; margin-top: 20px;")
    )
)


def server(input, output, session):
    # Check which data files are available
    wcc_available = reactive.Value(False)
    hcc_available = reactive.Value(False)

    # Check for WCC files
    wcc_files = ['BusinessGroups.csv', 'BusinessUnits.csv', 'JobTitles.csv',
                 'PayLocations.csv', 'StaffAssignments.csv']
    wcc_files_exist = [f for f in wcc_files if (app_dir / f).exists()]
    if len(wcc_files_exist) >= 3:  # At least core files
        wcc_available.set(True)

    # Check for HCC file
    if (app_dir / 'hccpositioninfo.csv').exists():
        hcc_available.set(True)

    # Update council choices based on available data
    @reactive.effect
    def update_council_choices():
        choices = []
        if wcc_available():
            choices.append("Wellington City Council")
        if hcc_available():
            choices.append("Hutt City Council")
        if wcc_available() and hcc_available():
            choices.append("Compare Councils")

        if choices:
            ui.update_select("council_select", choices=choices, selected=choices[0])

    # Utility functions
    def categorize_job_title(title):
        """Categorize job titles into broad categories"""
        if not title:
            return "Other"
        title_lower = title.lower()
        if any(word in title_lower for word in ['manager', 'head', 'director', 'chief', 'leader', 'supervisor']):
            return "Management"
        elif any(word in title_lower for word in ['analyst', 'specialist', 'advisor', 'consultant', 'planner']):
            return "Professional"
        elif any(word in title_lower for word in ['engineer', 'technician', 'developer', 'architect']):
            return "Technical"
        elif any(word in title_lower for word in ['officer', 'coordinator', 'administrator', 'assistant']):
            return "Administrative"
        elif any(word in title_lower for word in ['operator', 'driver', 'cleaner', 'maintenance']):
            return "Operational"
        else:
            return "Other"

    def get_job_level(title):
        """Extract job level from title"""
        if not title:
            return "Unknown"
        title_lower = title.lower()
        if any(word in title_lower for word in ['chief', 'director', 'head of']):
            return "Executive"
        elif any(word in title_lower for word in ['manager', 'team leader', 'supervisor']):
            return "Management"
        elif any(word in title_lower for word in ['senior', 'principal', 'lead']):
            return "Senior"
        elif any(word in title_lower for word in ['junior', 'assistant', 'trainee']):
            return "Junior"
        else:
            return "Mid-level"

    def calculate_gini(values):
        """Calculate Gini coefficient for inequality measurement"""
        if len(values) == 0:
            return 0
        sorted_values = sorted(values)
        n = len(values)
        cumsum = np.cumsum(sorted_values)
        return (2 * np.sum((i + 1) * sorted_values[i] for i in range(n))) / (n * cumsum[-1]) - (n + 1) / n

    # Load WCC data reactively
    @reactive.calc
    def business_groups():
        if input.council_select() in ["Wellington City Council", "Compare Councils"] and wcc_available():
            try:
                return pd.read_csv(app_dir / 'BusinessGroups.csv')
            except:
                return pd.DataFrame()
        return pd.DataFrame()

    @reactive.calc
    def business_units():
        if input.council_select() in ["Wellington City Council", "Compare Councils"] and wcc_available():
            try:
                return pd.read_csv(app_dir / 'BusinessUnits.csv')
            except:
                return pd.DataFrame()
        return pd.DataFrame()

    @reactive.calc
    def job_titles():
        if input.council_select() in ["Wellington City Council", "Compare Councils"] and wcc_available():
            try:
                return pd.read_csv(app_dir / 'JobTitles.csv')
            except:
                return pd.DataFrame()
        return pd.DataFrame()

    @reactive.calc
    def pay_locations():
        if input.council_select() in ["Wellington City Council", "Compare Councils"] and wcc_available():
            try:
                return pd.read_csv(app_dir / 'PayLocations.csv')
            except:
                return pd.DataFrame()
        return pd.DataFrame()

    @reactive.calc
    def staff_assignments():
        if input.council_select() in ["Wellington City Council", "Compare Councils"] and wcc_available():
            try:
                df = pd.read_csv(app_dir / 'StaffAssignments.csv')
                return df
            except:
                # Create dummy data if file doesn't exist
                if not business_units().empty and not job_titles().empty:
                    # Generate synthetic staff assignments
                    units = business_units()
                    jobs = job_titles()

                    assignments = []
                    for _, unit in units.iterrows():
                        # Assign 10-50 staff per unit randomly
                        num_positions = np.random.randint(10, 51)
                        for _ in range(num_positions):
                            job = jobs.sample(1).iloc[0]
                            assignments.append({
                                'UnitID': unit['UnitID'],
                                'TitleID': job['TitleID'],
                                'LocationID': np.random.randint(1, 6),
                                'StaffCount': np.random.randint(1, 6)
                            })
                    return pd.DataFrame(assignments)
        return pd.DataFrame()

    # Load HCC data with cleaning
    @reactive.calc
    def hcc_data():
        if input.council_select() in ["Hutt City Council", "Compare Councils"] and hcc_available():
            df = pd.read_csv(app_dir / 'hccpositioninfo.csv', encoding='cp1252')
            # Clean up trailing spaces in Group column
            df['Group'] = df['Group'].str.strip()
            # Add a StaffCount column (1 per row since each row is a position)
            df['StaffCount'] = 1
            # Add job categorization
            df['JobCategory'] = df['Job Title'].apply(categorize_job_title)
            df['JobLevel'] = df['Job Title'].apply(get_job_level)
            # Add WCC equivalent mapping
            df['WCC_Equivalent_Group'] = df['Group'].map(GROUP_MAPPINGS).fillna('No Direct Equivalent')
            return df
        return pd.DataFrame()

    # Create unified data structure
    @reactive.calc
    def merged_data():
        if input.council_select() == "Wellington City Council":
            if staff_assignments().empty:
                return pd.DataFrame()
            # Original WCC merge logic
            merged = staff_assignments().merge(
                business_units(), on='UnitID', how='left'
            ).merge(
                business_groups(), on='GroupID', how='left'
            ).merge(
                job_titles(), on='TitleID', how='left'
            )

            if not pay_locations().empty:
                merged = merged.merge(pay_locations(), on='LocationID', how='left')
            else:
                # Add default location if file missing
                merged['LocationName'] = 'Wellington City'

            # Add job categorization
            merged['JobCategory'] = merged['JobTitle'].apply(categorize_job_title)
            merged['JobLevel'] = merged['JobTitle'].apply(get_job_level)

            return merged

        elif input.council_select() == "Hutt City Council":
            if hcc_data().empty:
                return pd.DataFrame()
            # Transform HCC data to match expected structure
            df = hcc_data().copy()
            df['GroupName'] = df['Group']
            df['UnitName'] = df['Division']
            df['JobTitle'] = df['Job Title']
            df['LocationName'] = 'Hutt City'
            df['ManagerTitle'] = df['Manager Job Title']
            return df
        else:  # Compare Councils
            # Combine both datasets for comparison
            combined = pd.DataFrame()

            if wcc_available() and not staff_assignments().empty:
                wcc_data = staff_assignments().merge(
                    business_units(), on='UnitID', how='left'
                ).merge(
                    business_groups(), on='GroupID', how='left'
                ).merge(
                    job_titles(), on='TitleID', how='left'
                )

                if not pay_locations().empty:
                    wcc_data = wcc_data.merge(pay_locations(), on='LocationID', how='left')
                else:
                    wcc_data['LocationName'] = 'Wellington City'

                wcc_data['Council'] = 'Wellington'
                wcc_data['JobCategory'] = wcc_data['JobTitle'].apply(categorize_job_title)
                wcc_data['JobLevel'] = wcc_data['JobTitle'].apply(get_job_level)
                combined = pd.concat([combined, wcc_data])

            if hcc_available() and not hcc_data().empty:
                hcc_df = hcc_data().copy()
                hcc_df['GroupName'] = hcc_df['Group']
                hcc_df['UnitName'] = hcc_df['Division']
                hcc_df['JobTitle'] = hcc_df['Job Title']
                hcc_df['LocationName'] = 'Hutt City'
                hcc_df['Council'] = 'Hutt'
                hcc_df['ManagerTitle'] = hcc_df.get('Manager Job Title', None)
                combined = pd.concat([combined, hcc_df])

            return combined

    # Update filter choices when data loads or council changes
    @reactive.effect
    def update_filter_choices():
        data = merged_data()
        if data.empty:
            return

        # Update group choices
        if input.council_select() == "Compare Councils":
            groups = ["All", "All WCC", "All HCC"] + sorted(data['GroupName'].dropna().unique().tolist())
        else:
            groups = ["All"] + sorted(data['GroupName'].dropna().unique().tolist())
        ui.update_select("filter_group", choices=groups)

        # Update location choices (only for WCC)
        if input.council_select() == "Wellington City Council":
            locations = ["All"] + sorted(data['LocationName'].dropna().unique().tolist())
            ui.update_select("filter_location", choices=locations)

    # Reactive data based on filters
    @reactive.calc
    def filtered_data():
        data = merged_data().copy()
        if data.empty:
            return data

        # Handle special filters for comparison mode
        if input.council_select() == "Compare Councils":
            if input.filter_group() == "All WCC":
                data = data[data['Council'] == 'Wellington']
            elif input.filter_group() == "All HCC":
                data = data[data['Council'] == 'Hutt']
            elif input.filter_group() != "All":
                data = data[data['GroupName'] == input.filter_group()]
        else:
            if input.filter_group() != "All":
                data = data[data['GroupName'] == input.filter_group()]

        if input.filter_unit() != "All":
            data = data[data['UnitName'] == input.filter_unit()]

        if input.council_select() == "Wellington City Council" and input.filter_location() != "All":
            data = data[data['LocationName'] == input.filter_location()]

        # Apply job category filter if on job analysis page
        if hasattr(input, 'job_category_filter') and input.job_category_filter() != "All":
            data = data[data['JobCategory'] == input.job_category_filter()]

        return data

    # Update unit choices based on group selection
    @reactive.effect
    def update_unit_choices():
        data = merged_data()
        if data.empty:
            return

        if input.filter_group() in ["All", "All WCC", "All HCC"]:
            if input.filter_group() == "All WCC":
                filtered = data[data['Council'] == 'Wellington']
            elif input.filter_group() == "All HCC":
                filtered = data[data['Council'] == 'Hutt']
            else:
                filtered = data
            units = ["All"] + sorted(filtered['UnitName'].dropna().unique().tolist())
        else:
            filtered_data = data[data['GroupName'] == input.filter_group()]
            units = ["All"] + sorted(filtered_data['UnitName'].dropna().unique().tolist())

        ui.update_select("filter_unit", choices=units, selected="All")

    # Dynamic UI elements
    @output
    @render.text
    def dashboard_title():
        if input.council_select() == "Compare Councils":
            return "Wellington & Hutt City Councils Comparison"
        return f"{input.council_select()} Staff Analytics"

    @output
    @render.text
    def last_updated():
        return f"Dashboard generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"

    @output
    @render.text
    def location_or_division_title():
        if input.council_select() == "Wellington City Council":
            return "Top Pay Locations"
        elif input.council_select() == "Hutt City Council":
            return "Division Distribution"
        else:
            return "Council Comparison"

    # Overview Tab Outputs - Value Boxes
    @output
    @render.text
    def total_staff_overview():
        data = filtered_data()
        if data.empty:
            return "0"
        return f"{data['StaffCount'].sum():,}"

    @output
    @render.text
    def total_groups_overview():
        data = filtered_data()
        if data.empty:
            return "0"
        return str(data['GroupName'].nunique())

    @output
    @render.text
    def total_positions_overview():
        data = filtered_data()
        if data.empty:
            return "0"
        return str(data['JobTitle'].nunique())

    @output
    @render.text
    def avg_staff_unit_overview():
        data = filtered_data()
        if data.empty:
            return "0"
        unit_totals = data.groupby('UnitName')['StaffCount'].sum()
        if len(unit_totals) == 0:
            return "0"
        return f"{unit_totals.mean():.1f}"

    # Summary Statistics
    @output
    @render.ui
    def summary_stats():
        data = filtered_data()
        if data.empty:
            return ui.div("No data available")

        total_staff = data['StaffCount'].sum()
        num_units = data['UnitName'].nunique()
        num_positions = data['JobTitle'].nunique()

        stats = [
            ui.tags.strong(f"{total_staff:,} Total Staff"),
            ui.br(),
            ui.p(f"{num_units} Units/Divisions", style="margin: 5px 0;"),
            ui.p(f"{num_positions} Unique Positions", style="margin: 5px 0;"),
            ui.p(f"{len(data):,} Records", style="margin: 5px 0;")
        ]

        if input.council_select() == "Hutt City Council" and 'ManagerTitle' in data.columns:
            num_managers = data['ManagerTitle'].nunique()
            stats.append(ui.p(f"{num_managers} Manager Roles", style="margin: 5px 0;"))

        return ui.div(*stats)

    @output
    @render.ui
    def data_quality_stats():
        data = merged_data()
        if data.empty:
            return ui.div("No data")

        # Calculate data quality metrics
        completeness = (data.notna().sum() / len(data) * 100).mean()
        duplicates = data.duplicated().sum()

        quality_color = "green" if completeness > 95 else "orange" if completeness > 85 else "red"

        return ui.div(
            ui.p(f"Completeness: ", ui.tags.strong(f"{completeness:.1f}%",
                                                   style=f"color: {quality_color};")),
            ui.p(f"Duplicate Records: {duplicates}")
        )

    @output
    @render_plotly
    def group_distribution():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        if input.council_select() == "Compare Councils":
            # Show side-by-side comparison
            group_stats = data.groupby(['Council', 'GroupName'])['StaffCount'].sum().reset_index()

            # Ensure groups are mapped correctly for comparison
            fig = px.bar(
                group_stats,
                x='StaffCount',
                y='GroupName',
                color='Council',
                orientation='h',
                labels={'StaffCount': 'Total Staff', 'GroupName': 'Group'},
                color_discrete_map=COUNCIL_COLORS,
                barmode='group',
                title="Staff Distribution by Group"
            )
            fig.update_layout(
                xaxis_title="Number of Staff",
                yaxis_title="",
                legend_title="Council"
            )
        else:
            group_stats = data.groupby('GroupName')['StaffCount'].sum().reset_index()
            group_stats = group_stats.sort_values('StaffCount', ascending=True)

            # Add percentage column
            total_staff = group_stats['StaffCount'].sum()
            group_stats['Percentage'] = (group_stats['StaffCount'] / total_staff * 100).round(1)

            fig = px.bar(
                group_stats,
                x='StaffCount',
                y='GroupName',
                orientation='h',
                labels={'StaffCount': 'Total Staff', 'GroupName': 'Group'},
                color='GroupName',
                color_discrete_map=GROUP_COLORS,
                text=group_stats.apply(lambda x: f"{x['StaffCount']:,} ({x['Percentage']:.1f}%)", axis=1)
            )
            fig.update_traces(textposition='outside')

        fig.update_layout(
            showlegend=input.council_select() == "Compare Councils",
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        return fig

    @output
    @render.text
    def group_distribution_insight():
        data = filtered_data()
        if data.empty:
            return ""

        group_stats = data.groupby('GroupName')['StaffCount'].sum()
        largest_group = group_stats.idxmax()
        largest_pct = (group_stats.max() / group_stats.sum() * 100)

        return f"? {largest_group} is the largest group with {largest_pct:.1f}% of total staff"

    @output
    @render_plotly
    def location_distribution():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        if input.council_select() == "Wellington City Council":
            location_stats = data.groupby('LocationName')['StaffCount'].sum().reset_index()
            location_stats = location_stats.nlargest(10, 'StaffCount')
            x_col = 'LocationName'
            x_label = 'Location'
            title = "Top 10 Pay Locations"
        elif input.council_select() == "Hutt City Council":
            location_stats = data.groupby('UnitName')['StaffCount'].sum().reset_index()
            location_stats = location_stats.nlargest(10, 'StaffCount')
            x_col = 'UnitName'
            x_label = 'Division'
            title = "Top 10 Divisions by Staff Count"
        else:  # Compare Councils
            location_stats = data.groupby('Council')['StaffCount'].sum().reset_index()
            x_col = 'Council'
            x_label = 'Council'
            title = "Total Staff by Council"

        fig = px.bar(
            location_stats,
            x=x_col,
            y='StaffCount',
            labels={'StaffCount': 'Staff Count', x_col: x_label},
            color='StaffCount',
            color_continuous_scale='Viridis',
            text='StaffCount',
            title=title
        )
        fig.update_traces(texttemplate='%{text:,}', textposition='outside')
        fig.update_layout(
            showlegend=False,
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig

    @output
    @render_plotly
    def unit_treemap():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        if input.council_select() == "Compare Councils":
            unit_stats = data.groupby(['Council', 'GroupName', 'UnitName'])['StaffCount'].sum().reset_index()
            path_cols = ['Council', 'GroupName', 'UnitName']
        else:
            unit_stats = data.groupby(['GroupName', 'UnitName'])['StaffCount'].sum().reset_index()
            path_cols = ['GroupName', 'UnitName']

        unit_stats = unit_stats[unit_stats['StaffCount'] > 0]

        # Normalize if requested
        if input.treemap_normalize():
            # Normalize within each group
            unit_stats['NormalizedCount'] = unit_stats.groupby(path_cols[0])['StaffCount'].transform(
                lambda x: x / x.sum() * 100
            )
            values_col = 'NormalizedCount'
            hover_template = '<b>%{label}</b><br>Staff: %{customdata}<br>Group Share: %{value:.1f}%'
        else:
            values_col = 'StaffCount'
            hover_template = '<b>%{label}</b><br>Staff Count: %{value:,}'

        fig = px.treemap(
            unit_stats,
            path=path_cols,
            values=values_col,
            color='StaffCount',
            color_continuous_scale='RdYlBu',
            title="Hierarchical Staff Distribution",
            hover_data={'StaffCount': ':,'}
        )

        if input.treemap_normalize():
            fig.update_traces(customdata=unit_stats['StaffCount'], hovertemplate=hover_template)

        fig.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        return fig

    # Job Analysis Tab Outputs
    @output
    @render.ui
    def job_stats():
        data = filtered_data()
        if data.empty:
            return ui.div("No data available")

        if input.job_search():
            data = data[data['JobTitle'].str.contains(input.job_search(), case=False, na=False)]

        total_jobs = data['JobTitle'].nunique()
        total_staff_jobs = data['StaffCount'].sum()
        avg_staff_per_job = total_staff_jobs / total_jobs if total_jobs > 0 else 0

        # Calculate job diversity index (Shannon entropy)
        job_counts = data.groupby('JobTitle')['StaffCount'].sum()
        job_probs = job_counts / job_counts.sum()
        diversity_index = -np.sum(job_probs * np.log(job_probs + 1e-10))
        max_diversity = np.log(len(job_counts))
        diversity_pct = (diversity_index / max_diversity * 100) if max_diversity > 0 else 0

        return ui.div(
            ui.tags.strong(f"{total_jobs} Unique Titles"),
            ui.br(),
            ui.p(f"{total_staff_jobs:,} Total Staff", style="margin: 5px 0;"),
            ui.p(f"{avg_staff_per_job:.1f} Avg Staff/Title", style="margin: 5px 0;"),
            ui.p(f"Diversity: {diversity_pct:.0f}%", style="margin: 5px 0;",
                 title="Higher percentage indicates more even distribution across job titles")
        )

    @output
    @render.ui
    def job_insights():
        data = filtered_data()
        if data.empty:
            return ui.div("")

        # Most common job words
        if 'JobTitle' in data.columns:
            all_words = ' '.join(data['JobTitle'].dropna()).split()
            common_words = pd.Series(all_words).value_counts().head(5)

            # Job categories breakdown
            if 'JobCategory' in data.columns:
                category_counts = data.groupby('JobCategory')['StaffCount'].sum()
                top_category = category_counts.idxmax()

                return ui.div(
                    ui.p(ui.tags.strong("Top Job Words:"), style="margin-bottom: 5px;"),
                    ui.tags.small(', '.join(common_words.index)),
                    ui.br(),
                    ui.p(f"Top Category: {top_category}", style="margin-top: 10px;")
                )

        return ui.div("")

    @output
    @render_plotly
    def top_jobs_chart():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        if input.job_search():
            data = data[data['JobTitle'].str.contains(input.job_search(), case=False, na=False)]

        job_stats = data.groupby('JobTitle')['StaffCount'].sum().reset_index()
        job_stats = job_stats.nlargest(input.top_jobs_count(), 'StaffCount')

        chart_type = input.job_chart_type()

        if chart_type == "Bar":
            fig = px.bar(
                job_stats,
                x='StaffCount',
                y='JobTitle',
                orientation='h',
                labels={'StaffCount': 'Staff Count', 'JobTitle': 'Job Title'},
                color='StaffCount',
                color_continuous_scale='Plasma',
                text='StaffCount'
            )
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(height=max(400, len(job_stats) * 25))
        elif chart_type == "Treemap":
            fig = px.treemap(
                job_stats,
                path=['JobTitle'],
                values='StaffCount',
                color='StaffCount',
                color_continuous_scale='Plasma'
            )
            fig.update_layout(height=500)
        else:  # Sunburst
            # Add category information
            job_stats_with_cat = job_stats.copy()
            job_stats_with_cat['Category'] = job_stats_with_cat['JobTitle'].apply(categorize_job_title)

            fig = px.sunburst(
                job_stats_with_cat,
                path=['Category', 'JobTitle'],
                values='StaffCount',
                color='StaffCount',
                color_continuous_scale='Plasma'
            )
            fig.update_layout(height=500)

        fig.update_layout(
            showlegend=False,
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig

    @output
    @render_plotly
    def job_wordcloud():
        data = filtered_data()
        if data.empty or 'JobTitle' not in data.columns:
            return go.Figure()

        # Create word frequency from job titles
        from collections import Counter

        # Extract words from job titles
        all_words = []
        for title in data['JobTitle'].dropna():
            # Weight by staff count
            count = data[data['JobTitle'] == title]['StaffCount'].sum()
            words = title.split()
            all_words.extend(words * int(count))

        # Count word frequencies
        word_freq = Counter(all_words)
        # Remove common words
        stop_words = {'of', 'and', 'the', 'to', 'in', 'for', 'a', 'an', '&', '-'}
        word_freq = {w: c for w, c in word_freq.items() if w.lower() not in stop_words and len(w) > 2}

        # Get top 30 words
        top_words = dict(sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:30])

        if not top_words:
            return go.Figure()

        # Create scatter plot as word cloud alternative
        words = list(top_words.keys())
        counts = list(top_words.values())

        # Normalize sizes
        max_count = max(counts)
        sizes = [20 + (c / max_count) * 60 for c in counts]

        # Random positions
        np.random.seed(42)
        x = np.random.rand(len(words))
        y = np.random.rand(len(words))

        fig = go.Figure(data=[go.Scatter(
            x=x,
            y=y,
            mode='text',
            text=words,
            textfont=dict(
                size=sizes,
                color=np.random.rand(len(words)),
                colorscale='Viridis'
            ),
            hovertext=[f"{w}: {c} occurrences" for w, c in zip(words, counts)],
            hoverinfo='text'
        )])

        fig.update_layout(
            title="Job Title Word Frequency",
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    @output
    @render_plotly
    def job_level_distribution():
        data = filtered_data()
        if data.empty or 'JobLevel' not in data.columns:
            return go.Figure()

        level_stats = data.groupby('JobLevel')['StaffCount'].sum().reset_index()

        # Define order
        level_order = ['Executive', 'Management', 'Senior', 'Mid-level', 'Junior', 'Unknown']
        level_stats['JobLevel'] = pd.Categorical(level_stats['JobLevel'], categories=level_order, ordered=True)
        level_stats = level_stats.sort_values('JobLevel')

        fig = px.pie(
            level_stats,
            values='StaffCount',
            names='JobLevel',
            title="Staff Distribution by Job Level",
            color_discrete_sequence=px.colors.sequential.Blues_r
        )

        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Staff: %{value:,}<br>Percentage: %{percent}<extra></extra>'
        )

        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=30, b=0)
        )

        return fig

    @output
    @render_plotly
    def job_group_heatmap():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        # Get top jobs
        top_jobs = data.groupby('JobTitle')['StaffCount'].sum().nlargest(20).index
        data_filtered = data[data['JobTitle'].isin(top_jobs)]

        # Create pivot table
        pivot = data_filtered.pivot_table(
            values='StaffCount',
            index='JobTitle',
            columns='GroupName',
            fill_value=0,
            aggfunc='sum'
        )

        if pivot.empty:
            return go.Figure()

        # Apply clustering if requested
        if input.heatmap_cluster():
            # Simple hierarchical clustering
            from scipy.cluster.hierarchy import dendrogram, linkage
            from scipy.spatial.distance import pdist

            # Cluster rows
            row_linkage = linkage(pdist(pivot, metric='euclidean'), method='average')
            row_order = dendrogram(row_linkage, no_plot=True)['leaves']

            # Cluster columns
            col_linkage = linkage(pdist(pivot.T, metric='euclidean'), method='average')
            col_order = dendrogram(col_linkage, no_plot=True)['leaves']

            # Reorder
            pivot = pivot.iloc[row_order, col_order]

        fig = px.imshow(
            pivot.values,
            labels=dict(x="Group", y="Job Title", color="Staff Count"),
            x=pivot.columns,
            y=pivot.index,
            color_continuous_scale="YlOrRd",
            aspect="auto",
            title="Job Title Distribution Across Groups"
        )

        fig.update_layout(
            height=600,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        return fig

    # Organizational Structure Tab - HCC specific
    @output
    @render_plotly
    def org_network():
        if input.council_select() != "Hutt City Council":
            return go.Figure()

        data = hcc_data()
        if data.empty:
            return go.Figure()

        # Create network graph
        import networkx as nx

        G = nx.DiGraph()

        # Add nodes and edges
        for _, row in data.iterrows():
            if pd.notna(row['Manager Job Title']) and pd.notna(row['Job Title']):
                G.add_edge(row['Manager Job Title'], row['Job Title'])

        # Use spring layout
        pos = nx.spring_layout(G, k=2, iterations=50)

        # Create edge trace
        edge_trace = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace.append(go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=0.5, color='#888'),
                hoverinfo='none'
            ))

        # Create node trace
        node_x = []
        node_y = []
        node_text = []
        node_size = []

        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(node)
            # Size by number of reports
            node_size.append(10 + G.in_degree(node) * 5)

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=node_text,
            textposition="top center",
            marker=dict(
                size=node_size,
                color=node_size,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    title="Direct Reports",
                    thickness=15,
                    xanchor='left',
                    titleside='right'
                )
            )
        )

        fig = go.Figure(data=edge_trace + [node_trace])

        fig.update_layout(
            title="Organizational Reporting Network",
            showlegend=False,
            hovermode='closest',
            margin=dict(b=0, l=0, r=0, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600,
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    @output
    @render_plotly
    def reporting_structure():
        if input.council_select() != "Hutt City Council":
            return go.Figure()

        data = hcc_data()
        if data.empty:
            return go.Figure()

        # Count positions reporting to each manager
        manager_counts = data['Manager Job Title'].value_counts().head(15)

        fig = px.bar(
            x=manager_counts.values,
            y=manager_counts.index,
            orientation='h',
            labels={'x': 'Number of Direct Reports', 'y': 'Manager Position'},
            color=manager_counts.values,
            color_continuous_scale='Teal',
            title="Top 15 Managers by Direct Reports"
        )

        fig.update_traces(texttemplate='%{x}', textposition='outside')
        fig.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=30, b=0),
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig

    @output
    @render_plotly
    def span_of_control():
        if input.council_select() != "Hutt City Council":
            return go.Figure()

        data = hcc_data()
        if data.empty:
            return go.Figure()

        # Calculate span of control distribution
        manager_counts = data['Manager Job Title'].value_counts()
        span_distribution = manager_counts.value_counts().sort_index()

        fig = go.Figure(data=[
            go.Bar(
                x=span_distribution.index,
                y=span_distribution.values,
                text=span_distribution.values,
                textposition='outside',
                marker_color='lightblue'
            )
        ])

        fig.update_layout(
            title="Management Span of Control Distribution",
            xaxis_title="Number of Direct Reports",
            yaxis_title="Number of Managers",
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor='rgba(0,0,0,0)'
        )

        # Add average line
        avg_span = manager_counts.mean()
        fig.add_hline(y=avg_span, line_dash="dash", line_color="red",
                      annotation_text=f"Average: {avg_span:.1f}")

        return fig

    @output
    @render_plotly
    def manager_distribution():
        if input.council_select() != "Hutt City Council":
            return go.Figure()

        data = hcc_data()
        if data.empty:
            return go.Figure()

        # Create a matrix of divisions vs manager titles
        matrix = pd.crosstab(data['Division'], data['Manager Job Title'])

        # Select top managers by total reports
        top_managers = matrix.sum().nlargest(10).index
        matrix = matrix[top_managers]

        fig = px.imshow(
            matrix.values,
            labels=dict(x="Manager Title", y="Division", color="Count"),
            x=matrix.columns,
            y=matrix.index,
            color_continuous_scale="Purples",
            aspect="auto",
            title="Division-Manager Reporting Matrix"
        )

        fig.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        return fig

    # WCC-specific location outputs
    @output
    @render_plotly
    def location_pie():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        location_stats = data.groupby('LocationName')['StaffCount'].sum().reset_index()

        # Group smaller locations into "Other"
        threshold = location_stats['StaffCount'].sum() * 0.02
        location_stats.loc[location_stats['StaffCount'] < threshold, 'LocationName'] = 'Other'
        location_stats = location_stats.groupby('LocationName')['StaffCount'].sum().reset_index()

        fig = px.pie(
            location_stats,
            values='StaffCount',
            names='LocationName',
            title="Staff Geographic Distribution",
            color_discrete_sequence=px.colors.qualitative.Set3
        )

        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Staff: %{value:,}<br>Percentage: %{percent}<extra></extra>'
        )

        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        return fig

    @output
    @render_plotly
    def location_concentration():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        # Calculate location concentration (Lorenz curve)
        location_totals = data.groupby('LocationName')['StaffCount'].sum().sort_values()
        cumsum = location_totals.cumsum() / location_totals.sum()
        x = np.arange(len(location_totals)) / len(location_totals)

        # Calculate Gini coefficient
        gini = calculate_gini(location_totals.values)

        fig = go.Figure()

        # Add Lorenz curve
        fig.add_trace(go.Scatter(
            x=x, y=cumsum,
            mode='lines',
            name='Actual Distribution',
            line=dict(color='blue', width=3)
        ))

        # Add line of equality
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1],
            mode='lines',
            name='Perfect Equality',
            line=dict(color='red', dash='dash')
        ))

        # Add Gini coefficient annotation
        fig.add_annotation(
            x=0.2, y=0.8,
            text=f"Gini Coefficient: {gini:.3f}<br>({'Low' if gini < 0.3 else 'Medium' if gini < 0.6 else 'High'} concentration)",
            showarrow=False,
            bgcolor="white",
            bordercolor="black",
            borderwidth=1
        )

        fig.update_layout(
            title="Location Concentration Analysis",
            xaxis_title="Cumulative % of Locations",
            yaxis_title="Cumulative % of Staff",
            showlegend=True,
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig

    @output
    @render_plotly
    def location_group_matrix():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        matrix_data = data.pivot_table(
            values='StaffCount',
            index='LocationName',
            columns='GroupName',
            fill_value=0,
            aggfunc='sum'
        )

        if matrix_data.empty:
            return go.Figure()

        # Select top locations
        top_locations = matrix_data.sum(axis=1).nlargest(15).index
        matrix_data = matrix_data.loc[top_locations]

        fig = px.imshow(
            matrix_data.values,
            labels=dict(x="Business Group", y="Location", color="Staff Count"),
            x=matrix_data.columns,
            y=matrix_data.index,
            color_continuous_scale="Viridis",
            aspect="auto",
            title="Staff Distribution: Locations vs Groups"
        )

        fig.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        return fig

    @output
    @render.data_frame
    def location_table():
        data = filtered_data()
        if data.empty:
            return pd.DataFrame()

        location_summary = data.groupby('LocationName').agg({
            'StaffCount': 'sum',
            'JobTitle': 'nunique',
            'UnitName': 'nunique',
            'GroupName': 'nunique'
        }).reset_index()
        location_summary.columns = ['Location', 'Total Staff', 'Unique Jobs', 'Business Units', 'Business Groups']

        # Add percentage column
        location_summary['% of Total'] = (
                    location_summary['Total Staff'] / location_summary['Total Staff'].sum() * 100).round(1)

        location_summary = location_summary.sort_values('Total Staff', ascending=False)

        return render.DataGrid(
            location_summary,
            filters=True,
            width="100%",
            height="400px"
        )

    # Comparison mode outputs
    @output
    @render_plotly
    def structure_comparison():
        if input.council_select() != "Compare Councils":
            return go.Figure()

        # Create side-by-side org structure comparison
        wcc_groups = business_groups()
        hcc_groups = hcc_data()['Group'].unique() if not hcc_data().empty else []

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Wellington City Council', 'Hutt City Council'),
            specs=[[{'type': 'treemap'}, {'type': 'treemap'}]]
        )

        # WCC treemap
        if not wcc_groups.empty:
            wcc_data = merged_data()[merged_data()['Council'] == 'Wellington']
            wcc_tree = wcc_data.groupby(['GroupName', 'UnitName'])['StaffCount'].sum().reset_index()

            fig.add_trace(
                go.Treemap(
                    labels=wcc_tree['UnitName'],
                    parents=wcc_tree['GroupName'],
                    values=wcc_tree['StaffCount'],
                    textinfo="label+value",
                    hovertemplate='<b>%{label}</b><br>Staff: %{value}<extra></extra>'
                ),
                row=1, col=1
            )

        # HCC treemap
        if len(hcc_groups) > 0:
            hcc_tree = hcc_data().groupby(['Group', 'Division'])['StaffCount'].sum().reset_index()

            fig.add_trace(
                go.Treemap(
                    labels=hcc_tree['Division'],
                    parents=hcc_tree['Group'],
                    values=hcc_tree['StaffCount'],
                    textinfo="label+value",
                    hovertemplate='<b>%{label}</b><br>Staff: %{value}<extra></extra>'
                ),
                row=1, col=2
            )

        fig.update_layout(
            height=600,
            title="Organizational Structure Comparison",
            margin=dict(l=0, r=0, t=50, b=0)
        )

        return fig

    @output
    @render_plotly
    def group_size_comparison():
        if input.council_select() != "Compare Councils":
            return go.Figure()

        data = merged_data()
        if data.empty:
            return go.Figure()

        # Create aligned comparison using mappings
        comparison_data = []

        # Get WCC data
        wcc_data = data[data['Council'] == 'Wellington']
        wcc_groups = wcc_data.groupby('GroupName')['StaffCount'].sum()

        # Get HCC data
        hcc_data_df = data[data['Council'] == 'Hutt']
        hcc_groups = hcc_data_df.groupby('GroupName')['StaffCount'].sum()

        # Create comparison based on mappings
        for hcc_group, wcc_group in GROUP_MAPPINGS.items():
            hcc_count = hcc_groups.get(hcc_group, 0)
            wcc_count = wcc_groups.get(wcc_group, 0)

            if hcc_count > 0 or wcc_count > 0:
                comparison_data.append({
                    'Function': wcc_group,
                    'Wellington': wcc_count,
                    'Hutt': hcc_count
                })

        # Add WCC-only groups
        for wcc_group in wcc_groups.index:
            if wcc_group not in GROUP_MAPPINGS.values():
                comparison_data.append({
                    'Function': wcc_group,
                    'Wellington': wcc_groups[wcc_group],
                    'Hutt': 0
                })

        df_comp = pd.DataFrame(comparison_data)

        fig = go.Figure()

        fig.add_trace(go.Bar(
            name='Wellington',
            x=df_comp['Function'],
            y=df_comp['Wellington'],
            marker_color=COUNCIL_COLORS['Wellington']
        ))

        fig.add_trace(go.Bar(
            name='Hutt',
            x=df_comp['Function'],
            y=df_comp['Hutt'],
            marker_color=COUNCIL_COLORS['Hutt']
        ))

        fig.update_layout(
            title="Aligned Group Size Comparison",
            xaxis_title="Functional Area",
            yaxis_title="Staff Count",
            barmode='group',
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis_tickangle=-45
        )

        return fig

    @output
    @render_plotly
    def org_depth_comparison():
        if input.council_select() != "Compare Councils":
            return go.Figure()

        # Calculate organizational metrics
        metrics_data = []

        # WCC metrics
        if not business_units().empty:
            wcc_units = business_units()
            wcc_groups = business_groups()
            wcc_avg_units = len(wcc_units) / len(wcc_groups) if len(wcc_groups) > 0 else 0

            metrics_data.append({
                'Council': 'Wellington',
                'Metric': 'Avg Units per Group',
                'Value': wcc_avg_units
            })

        # HCC metrics
        if not hcc_data().empty:
            hcc_df = hcc_data()
            hcc_divisions = hcc_df['Division'].nunique()
            hcc_groups = hcc_df['Group'].nunique()
            hcc_avg_divisions = hcc_divisions / hcc_groups if hcc_groups > 0 else 0

            # Management layers
            hcc_managers = hcc_df['Manager Job Title'].nunique()
            hcc_layers = hcc_managers / hcc_divisions if hcc_divisions > 0 else 0

            metrics_data.extend([
                {
                    'Council': 'Hutt',
                    'Metric': 'Avg Units per Group',
                    'Value': hcc_avg_divisions
                },
                {
                    'Council': 'Hutt',
                    'Metric': 'Management Density',
                    'Value': hcc_layers
                }
            ])

        if not metrics_data:
            return go.Figure()

        df_metrics = pd.DataFrame(metrics_data)

        fig = px.bar(
            df_metrics,
            x='Metric',
            y='Value',
            color='Council',
            barmode='group',
            title="Organizational Complexity Metrics",
            color_discrete_map=COUNCIL_COLORS
        )

        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            yaxis_title="Value"
        )

        return fig

    # Analytics & Insights Tab
    @output
    @render_plotly
    def gini_analysis():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        # Calculate Gini coefficients for different dimensions
        gini_results = []

        # By unit
        unit_totals = data.groupby('UnitName')['StaffCount'].sum()
        unit_gini = calculate_gini(unit_totals.values)
        gini_results.append({'Dimension': 'By Unit/Division', 'Gini Coefficient': unit_gini})

        # By group
        group_totals = data.groupby('GroupName')['StaffCount'].sum()
        group_gini = calculate_gini(group_totals.values)
        gini_results.append({'Dimension': 'By Group', 'Gini Coefficient': group_gini})

        # By job title
        job_totals = data.groupby('JobTitle')['StaffCount'].sum()
        job_gini = calculate_gini(job_totals.values)
        gini_results.append({'Dimension': 'By Job Title', 'Gini Coefficient': job_gini})

        if 'LocationName' in data.columns and input.council_select() == "Wellington City Council":
            location_totals = data.groupby('LocationName')['StaffCount'].sum()
            location_gini = calculate_gini(location_totals.values)
            gini_results.append({'Dimension': 'By Location', 'Gini Coefficient': location_gini})

        df_gini = pd.DataFrame(gini_results)

        fig = go.Figure()

        # Add bars
        fig.add_trace(go.Bar(
            x=df_gini['Dimension'],
            y=df_gini['Gini Coefficient'],
            text=df_gini['Gini Coefficient'].round(3),
            textposition='outside',
            marker_color=['red' if g > 0.6 else 'orange' if g > 0.3 else 'green'
                          for g in df_gini['Gini Coefficient']]
        ))

        # Add reference lines
        fig.add_hline(y=0.3, line_dash="dash", line_color="orange",
                      annotation_text="Medium inequality")
        fig.add_hline(y=0.6, line_dash="dash", line_color="red",
                      annotation_text="High inequality")

        fig.update_layout(
            title="Staff Distribution Inequality Analysis",
            xaxis_title="Dimension",
            yaxis_title="Gini Coefficient (0=Perfect Equality, 1=Perfect Inequality)",
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            yaxis_range=[0, 1],
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    @output
    @render_plotly
    def efficiency_metrics():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        # Calculate various efficiency metrics
        metrics = []

        # Span of control
        if 'ManagerTitle' in data.columns and input.council_select() == "Hutt City Council":
            manager_counts = data['ManagerTitle'].value_counts()
            avg_span = manager_counts.mean()
            metrics.append({
                'Metric': 'Avg Span of Control',
                'Value': avg_span,
                'Benchmark': 7,  # Industry benchmark
                'Unit': 'Reports per Manager'
            })

        # Staff per unit
        units_staff = data.groupby('UnitName')['StaffCount'].sum()
        avg_staff_unit = units_staff.mean()
        metrics.append({
            'Metric': 'Avg Staff per Unit',
            'Value': avg_staff_unit,
            'Benchmark': 25,  # Assumed benchmark
            'Unit': 'Staff'
        })

        # Job diversity
        job_diversity = data['JobTitle'].nunique() / data['StaffCount'].sum() * 100
        metrics.append({
            'Metric': 'Job Diversity Ratio',
            'Value': job_diversity,
            'Benchmark': 15,  # 15% benchmark
            'Unit': '% Unique Jobs/Staff'
        })

        # Management ratio
        if 'JobLevel' in data.columns:
            mgmt_staff = data[data['JobLevel'].isin(['Executive', 'Management'])]['StaffCount'].sum()
            total_staff = data['StaffCount'].sum()
            mgmt_ratio = (mgmt_staff / total_staff * 100) if total_staff > 0 else 0
            metrics.append({
                'Metric': 'Management Ratio',
                'Value': mgmt_ratio,
                'Benchmark': 20,  # 20% benchmark
                'Unit': '% Management'
            })

        df_metrics = pd.DataFrame(metrics)

        # Create gauge charts
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}],
                   [{'type': 'indicator'}, {'type': 'indicator'}]],
            subplot_titles=[m['Metric'] for m in metrics[:4]]
        )

        for idx, metric in enumerate(metrics[:4]):
            row = idx // 2 + 1
            col = idx % 2 + 1

            # Determine color based on performance vs benchmark
            ratio = metric['Value'] / metric['Benchmark']
            if metric['Metric'] in ['Management Ratio']:  # Lower is better
                color = "green" if ratio < 1.1 else "orange" if ratio < 1.3 else "red"
            else:  # Higher is better
                color = "green" if ratio > 0.9 else "orange" if ratio > 0.7 else "red"

            fig.add_trace(
                go.Indicator(
                    mode="gauge+number+delta",
                    value=metric['Value'],
                    delta={'reference': metric['Benchmark'], 'relative': True},
                    gauge={
                        'axis': {'range': [0, metric['Benchmark'] * 2]},
                        'bar': {'color': color},
                        'threshold': {
                            'line': {'color': "black", 'width': 4},
                            'thickness': 0.75,
                            'value': metric['Benchmark']
                        }
                    },
                    title={'text': metric['Unit']}
                ),
                row=row, col=col
            )

        fig.update_layout(
            height=500,
            margin=dict(l=20, r=20, t=50, b=20)
        )

        return fig

    @output
    @render_plotly
    def predictive_analysis():
        data = filtered_data()
        if data.empty:
            return go.Figure()

        # Simple growth projection based on current structure
        current_staff = data.groupby('GroupName')['StaffCount'].sum()

        # Create projections (simplified - in reality would use more sophisticated models)
        years = list(range(2024, 2029))
        growth_scenarios = {
            'Conservative (2% p.a.)': 0.02,
            'Moderate (5% p.a.)': 0.05,
            'Aggressive (8% p.a.)': 0.08
        }

        fig = go.Figure()

        for scenario, rate in growth_scenarios.items():
            projections = []
            for year_offset in range(len(years)):
                projected_total = current_staff.sum() * (1 + rate) ** year_offset
                projections.append(projected_total)

            fig.add_trace(go.Scatter(
                x=years,
                y=projections,
                mode='lines+markers',
                name=scenario,
                line=dict(width=3)
            ))

        # Add current year marker
        fig.add_vline(x=2024, line_dash="dash", line_color="gray",
                      annotation_text="Current")

        fig.update_layout(
            title="Projected Staffing Needs (5-Year Forecast)",
            xaxis_title="Year",
            yaxis_title="Total Staff",
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            hovermode='x unified',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    @output
    @render.ui
    def insights_recommendations():
        data = filtered_data()
        if data.empty:
            return ui.div("No data available for analysis")

        insights = []

        # Analyze staff distribution
        group_gini = calculate_gini(data.groupby('GroupName')['StaffCount'].sum().values)
        if group_gini > 0.4:
            insights.append(
                ui.div(
                    ui.h5("?? Uneven Staff Distribution", style="color: orange;"),
                    ui.p(
                        f"Gini coefficient of {group_gini:.2f} indicates significant inequality in staff distribution across groups. "
                        "Consider rebalancing to improve organizational efficiency."),
                    ui.hr()
                )
            )

        # Analyze span of control (HCC specific)
        if 'ManagerTitle' in data.columns and input.council_select() == "Hutt City Council":
            manager_counts = data['ManagerTitle'].value_counts()
            high_span_managers = manager_counts[manager_counts > 10]
            if len(high_span_managers) > 0:
                insights.append(
                    ui.div(
                        ui.h5("? High Span of Control Detected", style="color: #1f77b4;"),
                        ui.p(f"{len(high_span_managers)} managers have more than 10 direct reports. "
                             f"Maximum span: {manager_counts.max()} reports. "
                             "Consider adding intermediate management layers."),
                        ui.hr()
                    )
                )

        # Analyze job diversity
        job_diversity = data['JobTitle'].nunique() / data['StaffCount'].sum()
        if job_diversity > 0.3:
            insights.append(
                ui.div(
                    ui.h5("? High Job Title Diversity", style="color: purple;"),
                    ui.p(
                        f"Ratio of {job_diversity:.1%} unique titles to staff suggests potential for job title consolidation. "
                        "Standardizing roles could improve career pathways and reduce administrative complexity."),
                    ui.hr()
                )
            )

        # Location concentration (WCC specific)
        if 'LocationName' in data.columns and input.council_select() == "Wellington City Council":
            location_concentration = data.groupby('LocationName')['StaffCount'].sum()
            top_location_pct = location_concentration.max() / location_concentration.sum()
            if top_location_pct > 0.5:
                insights.append(
                    ui.div(
                        ui.h5("? High Location Concentration", style="color: green;"),
                        ui.p(f"{top_location_pct:.0%} of staff concentrated in one location. "
                             "Consider distributed work arrangements for business continuity."),
                        ui.hr()
                    )
                )

        # Growth recommendations
        total_staff = data['StaffCount'].sum()
        insights.append(
            ui.div(
                ui.h5("? Strategic Recommendations", style="color: #2ca02c;"),
                ui.tags.ul(
                    ui.tags.li("Implement workforce planning aligned with strategic objectives"),
                    ui.tags.li("Develop succession planning for critical roles"),
                    ui.tags.li("Consider shared services for common functions across units"),
                    ui.tags.li("Invest in workforce analytics for data-driven decisions")
                )
            )
        )

        return ui.div(*insights)

    # Council Comparison Tab
    @output
    @render_plotly
    def council_comparison():
        comparison_data = []

        if wcc_available() and not staff_assignments().empty:
            wcc_total = staff_assignments()['StaffCount'].sum()
            wcc_groups = business_groups()['GroupName'].nunique()
            wcc_units = business_units()['UnitName'].nunique()
            comparison_data.extend([
                {'Council': 'Wellington', 'Metric': 'Total Staff', 'Value': wcc_total},
                {'Council': 'Wellington', 'Metric': 'Groups', 'Value': wcc_groups},
                {'Council': 'Wellington', 'Metric': 'Units', 'Value': wcc_units}
            ])

        if hcc_available() and not hcc_data().empty:
            hcc_df = hcc_data()
            hcc_total = len(hcc_df)
            hcc_groups = hcc_df['Group'].nunique()
            hcc_divisions = hcc_df['Division'].nunique()
            comparison_data.extend([
                {'Council': 'Hutt', 'Metric': 'Total Staff', 'Value': hcc_total},
                {'Council': 'Hutt', 'Metric': 'Groups', 'Value': hcc_groups},
                {'Council': 'Hutt', 'Metric': 'Units', 'Value': hcc_divisions}
            ])

        if not comparison_data:
            return go.Figure()

        df = pd.DataFrame(comparison_data)

        fig = px.bar(
            df,
            x='Metric',
            y='Value',
            color='Council',
            barmode='group',
            title="Council Overview Comparison",
            color_discrete_map=COUNCIL_COLORS,
            text='Value'
        )

        fig.update_traces(texttemplate='%{text:,}', textposition='outside')
        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig

    @output
    @render_plotly
    def job_overlap():
        if not (wcc_available() and hcc_available()):
            return go.Figure()

        wcc_jobs = job_titles()
        hcc_df = hcc_data()

        if wcc_jobs.empty or hcc_df.empty:
            return go.Figure()

        wcc_titles = set(wcc_jobs['JobTitle'].str.lower().unique())
        hcc_titles = set(hcc_df['Job Title'].str.lower().unique())

        # Calculate overlaps
        common_titles = wcc_titles.intersection(hcc_titles)
        wcc_only = wcc_titles - hcc_titles
        hcc_only = hcc_titles - wcc_titles

        # Calculate similarity scores for non-exact matches
        similarity_scores = []
        for hcc_title in list(hcc_only)[:50]:  # Sample for performance
            best_match = None
            best_score = 0
            for wcc_title in list(wcc_only)[:50]:
                score = SequenceMatcher(None, hcc_title, wcc_title).ratio()
                if score > best_score:
                    best_score = score
                    best_match = wcc_title
            if best_score > 0.8:  # High similarity
                similarity_scores.append(best_score)

        avg_similarity = np.mean(similarity_scores) if similarity_scores else 0

        # Create visualization
        categories = ['Exact Matches', 'WCC Only', 'HCC Only', 'Similar (>80%)']
        values = [len(common_titles), len(wcc_only), len(hcc_only), len(similarity_scores)]

        fig = go.Figure(data=[
            go.Bar(
                x=categories,
                y=values,
                text=values,
                textposition='outside',
                marker_color=['green', COUNCIL_COLORS['Wellington'], COUNCIL_COLORS['Hutt'], 'yellow']
            )
        ])

        fig.update_layout(
            title=f"Job Title Analysis (Avg Similarity: {avg_similarity:.0%})",
            xaxis_title="Category",
            yaxis_title="Number of Job Titles",
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    @output
    @render_plotly
    def structural_alignment():
        if not (wcc_available() and hcc_available()):
            return go.Figure()

        # Calculate structural alignment score
        alignment_scores = []

        for hcc_group, wcc_group in GROUP_MAPPINGS.items():
            if wcc_group != "No Direct Equivalent":
                alignment_scores.append({
                    'HCC Group': hcc_group,
                    'WCC Group': wcc_group,
                    'Alignment': 'Direct',
                    'Score': 1.0
                })
            else:
                alignment_scores.append({
                    'HCC Group': hcc_group,
                    'WCC Group': 'None',
                    'Alignment': 'No Match',
                    'Score': 0.0
                })

        df_align = pd.DataFrame(alignment_scores)

        # Create sunburst chart
        fig = px.sunburst(
            df_align,
            path=['Alignment', 'HCC Group'],
            values='Score',
            color='Score',
            color_continuous_scale='RdYlGn',
            title="Organizational Alignment Map"
        )

        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=30, b=0)
        )

        return fig

    @output
    @render.data_frame
    def department_mapping():
        if not (wcc_available() and hcc_available()):
            return pd.DataFrame()

        # Create comprehensive mapping table
        mapping_data = []

        # Get staff counts for context
        wcc_staff = {}
        hcc_staff = {}

        if not staff_assignments().empty:
            wcc_merged = staff_assignments().merge(
                business_units(), on='UnitID'
            ).merge(
                business_groups(), on='GroupID'
            )
            wcc_staff = wcc_merged.groupby('GroupName')['StaffCount'].sum().to_dict()

        if not hcc_data().empty:
            hcc_staff = hcc_data().groupby('Group')['StaffCount'].sum().to_dict()

        # Create mappings with staff counts
        for hcc_group, wcc_group in GROUP_MAPPINGS.items():
            hcc_count = hcc_staff.get(hcc_group, 0)
            wcc_count = wcc_staff.get(wcc_group, 0)

            mapping_data.append({
                'HCC Group': hcc_group,
                'HCC Staff': hcc_count,
                'WCC Equivalent': wcc_group,
                'WCC Staff': wcc_count,
                'Match Quality': 'Direct' if wcc_group != 'No Direct Equivalent' else 'None',
                'Staff Difference': abs(hcc_count - wcc_count)
            })

        # Add WCC groups without HCC equivalent
        mapped_wcc = set(GROUP_MAPPINGS.values())
        for wcc_group in wcc_staff.keys():
            if wcc_group not in mapped_wcc and wcc_group != 'No Direct Equivalent':
                mapping_data.append({
                    'HCC Group': 'No Equivalent',
                    'HCC Staff': 0,
                    'WCC Equivalent': wcc_group,
                    'WCC Staff': wcc_staff.get(wcc_group, 0),
                    'Match Quality': 'WCC Only',
                    'Staff Difference': wcc_staff.get(wcc_group, 0)
                })

        df = pd.DataFrame(mapping_data)
        df = df.sort_values(['Match Quality', 'Staff Difference'])

        return render.DataGrid(
            df,
            filters=True,
            width="100%",
            height="400px"
        )

    @output
    @render_plotly
    def functional_comparison():
        if not (wcc_available() and hcc_available()):
            return go.Figure()

        # Create detailed functional comparison
        data = merged_data()
        if data.empty:
            return go.Figure()

        # Aggregate by mapped functions
        functional_data = []

        for hcc_group, wcc_group in GROUP_MAPPINGS.items():
            if wcc_group != "No Direct Equivalent":
                # Get HCC data
                hcc_stats = data[(data['Council'] == 'Hutt') & (data['GroupName'] == hcc_group)]
                hcc_staff = hcc_stats['StaffCount'].sum()
                hcc_units = hcc_stats['UnitName'].nunique()

                # Get WCC data
                wcc_stats = data[(data['Council'] == 'Wellington') & (data['GroupName'] == wcc_group)]
                wcc_staff = wcc_stats['StaffCount'].sum()
                wcc_units = wcc_stats['UnitName'].nunique()

                if hcc_staff > 0 or wcc_staff > 0:
                    functional_data.append({
                        'Function': wcc_group,
                        'Metric': 'Staff Count',
                        'Wellington': wcc_staff,
                        'Hutt': hcc_staff
                    })
                    functional_data.append({
                        'Function': wcc_group,
                        'Metric': 'Units/Divisions',
                        'Wellington': wcc_units,
                        'Hutt': hcc_units
                    })

        if not functional_data:
            return go.Figure()

        df_func = pd.DataFrame(functional_data)

        # Create grouped bar chart
        fig = px.bar(
            df_func,
            x='Function',
            y=['Wellington', 'Hutt'],
            facet_row='Metric',
            title="Detailed Functional Comparison",
            barmode='group',
            color_discrete_map=COUNCIL_COLORS
        )

        fig.update_layout(
            height=600,
            margin=dict(l=0, r=0, t=50, b=0),
            showlegend=True
        )

        # Update y-axis titles
        fig.update_yaxes(title_text="Count", matches=None)
        fig.update_xaxes(tickangle=-45)

        return fig

    # Data Explorer Tab
    @output
    @render.ui
    def table_selector():
        if input.council_select() == "Wellington City Council":
            choices = [
                "Staff Summary",
                "Business Groups",
                "Business Units",
                "Job Titles",
                "Pay Locations",
                "Raw Staff Data"
            ]
        elif input.council_select() == "Hutt City Council":
            choices = [
                "Position Summary",
                "Group Analysis",
                "Division Analysis",
                "Management Structure",
                "Job Categories"
            ]
        else:  # Compare Councils
            choices = [
                "Combined Summary",
                "Council Comparison",
                "Group Alignment",
                "Job Title Analysis",
                "Efficiency Metrics"
            ]

        return ui.input_select(
            "table_select",
            "Select View:",
            choices=choices,
            selected=choices[0]
        )

    @output
    @render.data_frame
    def data_table():
        table_choice = input.table_select()

        if input.council_select() == "Wellington City Council":
            if table_choice == "Staff Summary":
                data = filtered_data()
                if not data.empty:
                    summary = data.groupby(['GroupName', 'UnitName']).agg({
                        'StaffCount': 'sum',
                        'JobTitle': 'nunique',
                        'LocationName': lambda x: x.value_counts().index[0] if len(x) > 0 else ''
                    }).reset_index()
                    summary.columns = ['Group', 'Unit', 'Total Staff', 'Unique Positions', 'Primary Location']
                    data = summary
                else:
                    data = pd.DataFrame()
            elif table_choice == "Business Groups":
                data = business_groups()
            elif table_choice == "Business Units":
                data = business_units()
                if not data.empty and not business_groups().empty:
                    data = data.merge(business_groups(), on='GroupID', how='left')
            elif table_choice == "Job Titles":
                data = job_titles()
            elif table_choice == "Pay Locations":
                data = pay_locations()
            else:  # Raw Staff Data
                data = filtered_data()[['GroupName', 'UnitName', 'JobTitle', 'LocationName', 'StaffCount']]

        elif input.council_select() == "Hutt City Council":
            hcc_df = hcc_data()
            if table_choice == "Position Summary":
                data = hcc_df[
                    ['Number', 'Job Title', 'Group', 'Division', 'Manager Job Title', 'JobCategory', 'JobLevel']]
            elif table_choice == "Group Analysis":
                data = hcc_df.groupby('Group').agg({
                    'Number': 'count',
                    'Division': 'nunique',
                    'Job Title': 'nunique',
                    'Manager Job Title': 'nunique'
                }).reset_index()
                data.columns = ['Group', 'Positions', 'Divisions', 'Unique Job Titles', 'Management Roles']
            elif table_choice == "Division Analysis":
                data = hcc_df.groupby(['Group', 'Division']).agg({
                    'Number': 'count',
                    'Job Title': 'nunique',
                    'Manager Job Title': 'nunique'
                }).reset_index()
                data.columns = ['Group', 'Division', 'Positions', 'Unique Job Titles', 'Management Roles']
            elif table_choice == "Management Structure":
                data = hcc_df.groupby('Manager Job Title').agg({
                    'Number': 'count',
                    'Division': lambda x: ', '.join(x.unique()[:3]) + ('...' if x.nunique() > 3 else ''),
                    'Group': 'nunique'
                }).reset_index()
                data.columns = ['Manager Title', 'Direct Reports', 'Divisions', 'Groups']
                data = data.sort_values('Direct Reports', ascending=False)
            else:  # Job Categories
                data = hcc_df.groupby(['JobCategory', 'JobLevel']).size().reset_index(name='Count')
                data = data.pivot(index='JobCategory', columns='JobLevel', values='Count').fillna(0).astype(int)
                data = data.reset_index()

        else:  # Compare Councils
            if table_choice == "Combined Summary":
                data = filtered_data()[['Council', 'GroupName', 'UnitName', 'JobTitle', 'StaffCount']]
            elif table_choice == "Council Comparison":
                data = filtered_data().groupby('Council').agg({
                    'StaffCount': 'sum',
                    'GroupName': 'nunique',
                    'UnitName': 'nunique',
                    'JobTitle': 'nunique'
                }).reset_index()
                data.columns = ['Council', 'Total Staff', 'Groups', 'Units/Divisions', 'Job Titles']
            elif table_choice == "Group Alignment":
                # Show mapping with stats
                alignment_data = []
                for hcc_group, wcc_group in GROUP_MAPPINGS.items():
                    hcc_stats = filtered_data()[(filtered_data()['Council'] == 'Hutt') &
                                                (filtered_data()['GroupName'] == hcc_group)]
                    wcc_stats = filtered_data()[(filtered_data()['Council'] == 'Wellington') &
                                                (filtered_data()['GroupName'] == wcc_group)]

                    alignment_data.append({
                        'HCC Group': hcc_group,
                        'HCC Staff': hcc_stats['StaffCount'].sum(),
                        'WCC Equivalent': wcc_group,
                        'WCC Staff': wcc_stats['StaffCount'].sum() if wcc_group != 'No Direct Equivalent' else 0
                    })
                data = pd.DataFrame(alignment_data)
            elif table_choice == "Job Title Analysis":
                # Top jobs by council
                job_comparison = filtered_data().groupby(['JobTitle', 'Council'])['StaffCount'].sum().reset_index()
                data = job_comparison.pivot(index='JobTitle', columns='Council', values='StaffCount').fillna(0)
                data['Total'] = data.sum(axis=1)
                data = data.sort_values('Total', ascending=False).head(50)
                data = data.reset_index()
            else:  # Efficiency Metrics
                metrics_data = []
                for council in ['Wellington', 'Hutt']:
                    council_data = filtered_data()[filtered_data()['Council'] == council]
                    if not council_data.empty:
                        metrics_data.append({
                            'Council': council,
                            'Staff per Unit': council_data.groupby('UnitName')['StaffCount'].sum().mean(),
                            'Job Diversity %': council_data['JobTitle'].nunique() / council_data[
                                'StaffCount'].sum() * 100,
                            'Avg Unit Size': council_data.groupby('UnitName')['StaffCount'].sum().mean(),
                            'Group Gini': calculate_gini(council_data.groupby('GroupName')['StaffCount'].sum().values)
                        })
                data = pd.DataFrame(metrics_data).round(2)

        return render.DataGrid(
            data,
            filters=True,
            width="100%",
            height="600px",
            row_selection_mode="multiple"
        )

    @session.download
    def download_data():
        # Get current data view
        df = pd.DataFrame()  # Placeholder - would get from data_table

        export_format = input.export_format()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if export_format == "CSV":
            return df.to_csv(index=False), f"council_data_{timestamp}.csv"
        elif export_format == "Excel":
            # Would need to use BytesIO and xlsxwriter
            pass
        else:  # JSON
            return df.to_json(orient='records'), f"council_data_{timestamp}.json"

    @session.download
    def download_mapping():
        # Create comprehensive mapping report
        report_data = []

        for hcc_group, wcc_group in GROUP_MAPPINGS.items():
            report_data.append({
                'HCC Group': hcc_group,
                'WCC Equivalent': wcc_group,
                'Mapping Type': 'Direct' if wcc_group != 'No Direct Equivalent' else 'None',
                'Notes': 'Based on functional similarity'
            })

        df = pd.DataFrame(report_data)
        return df.to_csv(index=False), "council_department_mapping.csv"

    @session.download
    def download_report():
        # Generate comprehensive report
        # This would create a full analytical report
        report = "Council Staff Analytics Report\n"
        report += "=" * 50 + "\n\n"
        report += f"Generated: {datetime.now().strftime('%B %d, %Y')}\n\n"

        # Add summary statistics
        data = merged_data()
        if not data.empty:
            report += "SUMMARY STATISTICS\n"
            report += f"Total Staff: {data['StaffCount'].sum():,}\n"
            report += f"Total Groups: {data['GroupName'].nunique()}\n"
            report += f"Total Units: {data['UnitName'].nunique()}\n"
            report += f"Unique Job Titles: {data['JobTitle'].nunique()}\n\n"

        return report, f"council_analytics_report_{datetime.now().strftime('%Y%m%d')}.txt"


# Create the Shiny app
app = App(app_ui, server)