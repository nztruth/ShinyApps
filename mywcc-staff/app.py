from shiny import App, ui, render, reactive
from shiny.types import ImgData
from shinywidgets import render_plotly, output_widget  # Added output_widget for correctness
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from pathlib import Path

# Get the directory where this script is located
app_dir = Path(__file__).parent

# Define the UI
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Overview",
        ui.layout_sidebar(
            ui.sidebar(
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
                    "Business Unit:",
                    choices=["All"],
                    selected="All",
                    multiple=False
                ),
                ui.input_select(
                    "filter_location",
                    "Pay Location:",
                    choices=["All"],
                    selected="All",
                    multiple=False
                ),
                ui.hr(),
                ui.h5("Summary Statistics"),
                ui.output_ui("summary_stats"),
                width=300
            ),
            ui.row(
                ui.column(
                    12,
                    ui.h2("Wellington City Council Staff Analytics Dashboard"),
                    ui.hr()
                )
            ),
            ui.row(
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Staff Distribution by Business Group"),
                        output_widget("group_distribution")
                    )
                ),
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Top 10 Pay Locations by Staff Count"),
                        output_widget("location_distribution")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Staff Count by Business Unit"),
                        output_widget("unit_treemap")
                    )
                )
            )
        )
    ),
    ui.nav_panel(
        "Job Analysis",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Job Title Search"),
                ui.input_text(
                    "job_search",
                    "Search Job Titles:",
                    placeholder="Enter keyword..."
                ),
                ui.input_slider(
                    "top_jobs_count",
                    "Number of Top Jobs to Show:",
                    min=5,
                    max=50,
                    value=20,
                    step=5
                ),
                ui.hr(),
                ui.h5("Job Statistics"),
                ui.output_ui("job_stats"),
                width=300
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Top Job Titles by Staff Count"),
                        output_widget("top_jobs_chart")
                    )
                )
            ),
            ui.row(
                ui.column(
                    12,
                    ui.card(
                        ui.card_header("Job Title Distribution Across Business Groups"),
                        output_widget("job_group_heatmap")
                    )
                )
            )
        )
    ),
    ui.nav_panel(
        "Location Analysis",
        ui.row(
            ui.column(
                6,
                ui.card(
                    ui.card_header("Staff Distribution Across Locations"),
                    output_widget("location_pie")
                )
            ),
            ui.column(
                6,
                ui.card(
                    ui.card_header("Location vs Business Group Matrix"),
                    output_widget("location_group_matrix")
                )
            )
        ),
        ui.row(
            ui.column(
                12,
                ui.card(
                    ui.card_header("Detailed Location Statistics"),
                    ui.output_data_frame("location_table")
                )
            )
        )
    ),
    ui.nav_panel(
        "Data Explorer",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Data Table Selection"),
                ui.input_select(
                    "table_select",
                    "Select Table:",
                    choices=[
                        "Merged Data (All Tables Combined)",
                        "Business Groups",
                        "Business Units",
                        "Job Titles",
                        "Pay Locations",
                        "Staff Assignments"
                    ],
                    selected="Merged Data (All Tables Combined)"
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
                ui.download_button(
                    "download_data",
                    "Download Current View"
                ),
                width=300
            ),
            ui.card(
                ui.card_header("Data Table"),
                ui.output_data_frame("data_table")
            )
        )
    ),
    ui.nav_panel(
        "Insights",
        ui.row(
            ui.column(
                12,
                ui.h3("Key Insights and Metrics"),
                ui.hr()
            )
        ),
        ui.row(
            ui.column(
                3,
                ui.value_box(
                    "Total Staff",
                    ui.output_text("total_staff"),
                    showcase=ui.span("?", style="font-size: 3rem;"),
                    theme="primary"
                )
            ),
            ui.column(
                3,
                ui.value_box(
                    "Total Positions",
                    ui.output_text("total_positions"),
                    showcase=ui.span("?", style="font-size: 3rem;"),
                    theme="success"
                )
            ),
            ui.column(
                3,
                ui.value_box(
                    "Avg Staff per Unit",
                    ui.output_text("avg_staff_unit"),
                    showcase=ui.span("?", style="font-size: 3rem;"),
                    theme="info"
                )
            ),
            ui.column(
                3,
                ui.value_box(
                    "Locations",
                    ui.output_text("total_locations"),
                    showcase=ui.span("?", style="font-size: 3rem;"),
                    theme="warning"
                )
            )
        ),
        ui.row(
            ui.column(
                6,
                ui.card(
                    ui.card_header("Staff Concentration Analysis"),
                    output_widget("concentration_chart")
                )
            ),
            ui.column(
                6,
                ui.card(
                    ui.card_header("Business Group Composition"),
                    output_widget("group_composition")
                )
            )
        )
    ),
    title="WCC Staff Data Dashboard",
    bg="#343a40",
    inverse=True
)


def server(input, output, session):
    # Load data reactively
    @reactive.calc
    def business_groups():
        return pd.read_csv(app_dir / 'BusinessGroups.csv')

    @reactive.calc
    def business_units():
        return pd.read_csv(app_dir / 'BusinessUnits.csv')

    @reactive.calc
    def job_titles():
        return pd.read_csv(app_dir / 'JobTitles.csv')

    @reactive.calc
    def pay_locations():
        return pd.read_csv(app_dir / 'PayLocations.csv')

    @reactive.calc
    def staff_assignments():
        return pd.read_csv(app_dir / 'StaffAssignments.csv')

    @reactive.calc
    def merged_data():
        # Create a merged dataset for easier analysis
        return staff_assignments().merge(
            business_units(), on='UnitID', how='left'
        ).merge(
            business_groups(), on='GroupID', how='left'
        ).merge(
            job_titles(), on='TitleID', how='left'
        ).merge(
            pay_locations(), on='LocationID', how='left'
        )

    # Update filter choices when data loads
    @reactive.effect
    def update_initial_choices():
        # Update business group choices
        groups = ["All"] + sorted(business_groups()['GroupName'].unique().tolist())
        ui.update_select("filter_group", choices=groups)

        # Update location choices
        locations = ["All"] + sorted(pay_locations()['LocationName'].unique().tolist())
        ui.update_select("filter_location", choices=locations)

    # Reactive data based on filters
    @reactive.calc
    def filtered_data():
        data = merged_data().copy()

        if input.filter_group() != "All":
            data = data[data['GroupName'] == input.filter_group()]

        if input.filter_unit() != "All":
            data = data[data['UnitName'] == input.filter_unit()]

        if input.filter_location() != "All":
            data = data[data['LocationName'] == input.filter_location()]

        return data

    # Update business unit choices based on group selection
    @reactive.effect
    def update_unit_choices():
        if input.filter_group() == "All":
            units = ["All"] + sorted(business_units()['UnitName'].unique().tolist())
        else:
            group_id = business_groups()[business_groups()['GroupName'] == input.filter_group()]['GroupID'].iloc[0]
            filtered_units = business_units()[business_units()['GroupID'] == group_id]
            units = ["All"] + sorted(filtered_units['UnitName'].unique().tolist())

        ui.update_select("filter_unit", choices=units, selected="All")

    # Overview Tab Outputs
    @output
    @render.ui
    def summary_stats():
        data = filtered_data()
        total_staff = data['StaffCount'].sum()
        num_units = data['UnitName'].nunique()
        num_positions = data['JobTitle'].nunique()

        return ui.div(
            ui.p(f"Total Staff: {total_staff:,}", style="font-weight: bold;"),
            ui.p(f"Business Units: {num_units}"),
            ui.p(f"Unique Positions: {num_positions}"),
            ui.p(f"Records: {len(data):,}")
        )

    @output
    @render_plotly
    def group_distribution():
        data = filtered_data()
        group_stats = data.groupby('GroupName')['StaffCount'].sum().reset_index()
        group_stats = group_stats.sort_values('StaffCount', ascending=True)

        fig = px.bar(
            group_stats,
            x='StaffCount',
            y='GroupName',
            orientation='h',
            labels={'StaffCount': 'Total Staff', 'GroupName': 'Business Group'},
            color='StaffCount',
            color_continuous_scale='Blues'
        )
        fig.update_layout(
            showlegend=False,
            height=400,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        return fig

    @output
    @render_plotly
    def location_distribution():
        data = filtered_data()
        location_stats = data.groupby('LocationName')['StaffCount'].sum().reset_index()
        location_stats = location_stats.nlargest(10, 'StaffCount')

        fig = px.bar(
            location_stats,
            x='LocationName',
            y='StaffCount',
            labels={'StaffCount': 'Staff Count', 'LocationName': 'Location'},
            color='StaffCount',
            color_continuous_scale='Viridis',
            text='StaffCount'
        )
        fig.update_traces(texttemplate='%{text}', textposition='outside')
        fig.update_layout(
            showlegend=False,
            height=400,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis_tickangle=-45
        )
        return fig

    @output
    @render_plotly
    def unit_treemap():
        data = filtered_data()
        unit_stats = data.groupby(['GroupName', 'UnitName'])['StaffCount'].sum().reset_index()

        fig = px.treemap(
            unit_stats,
            path=['GroupName', 'UnitName'],
            values='StaffCount',
            color='StaffCount',
            color_continuous_scale='RdYlBu',
            title=None
        )
        fig.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        return fig

    # Job Analysis Tab Outputs
    @output
    @render.ui
    def job_stats():
        data = filtered_data()
        if input.job_search():
            data = data[data['JobTitle'].str.contains(input.job_search(), case=False, na=False)]

        total_jobs = data['JobTitle'].nunique()
        total_staff_jobs = data['StaffCount'].sum()
        avg_staff_per_job = total_staff_jobs / total_jobs if total_jobs > 0 else 0

        return ui.div(
            ui.p(f"Unique Job Titles: {total_jobs}", style="font-weight: bold;"),
            ui.p(f"Total Staff: {total_staff_jobs:,}"),
            ui.p(f"Avg Staff/Title: {avg_staff_per_job:.1f}")
        )

    @output
    @render_plotly
    def top_jobs_chart():
        data = filtered_data()
        if input.job_search():
            data = data[data['JobTitle'].str.contains(input.job_search(), case=False, na=False)]

        job_stats = data.groupby('JobTitle')['StaffCount'].sum().reset_index()
        job_stats = job_stats.nlargest(input.top_jobs_count(), 'StaffCount')

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
        fig.update_traces(texttemplate='%{text}', textposition='outside')
        fig.update_layout(
            showlegend=False,
            height=max(400, len(job_stats) * 25),
            margin=dict(l=0, r=0, t=0, b=0)
        )
        return fig

    @output
    @render_plotly
    def job_group_heatmap():
        data = filtered_data()

        # Get top 20 jobs by staff count
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

        fig = px.imshow(
            pivot.values,
            labels=dict(x="Business Group", y="Job Title", color="Staff Count"),
            x=pivot.columns,
            y=pivot.index,
            color_continuous_scale="YlOrRd",
            aspect="auto"
        )
        fig.update_layout(
            height=600,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        return fig

    # Location Analysis Tab Outputs
    @output
    @render_plotly
    def location_pie():
        data = filtered_data()
        location_stats = data.groupby('LocationName')['StaffCount'].sum().reset_index()

        # Group smaller locations into "Other"
        threshold = location_stats['StaffCount'].sum() * 0.02
        location_stats.loc[location_stats['StaffCount'] < threshold, 'LocationName'] = 'Other'
        location_stats = location_stats.groupby('LocationName')['StaffCount'].sum().reset_index()

        fig = px.pie(
            location_stats,
            values='StaffCount',
            names='LocationName',
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        return fig

    @output
    @render_plotly
    def location_group_matrix():
        data = filtered_data()
        matrix_data = data.pivot_table(
            values='StaffCount',
            index='LocationName',
            columns='GroupName',
            fill_value=0,
            aggfunc='sum'
        )

        # Select top 15 locations by total staff
        top_locations = matrix_data.sum(axis=1).nlargest(15).index
        matrix_data = matrix_data.loc[top_locations]

        fig = px.imshow(
            matrix_data.values,
            labels=dict(x="Business Group", y="Location", color="Staff Count"),
            x=matrix_data.columns,
            y=matrix_data.index,
            color_continuous_scale="Viridis",
            aspect="auto"
        )
        fig.update_layout(
            height=500,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        return fig

    @output
    @render.data_frame
    def location_table():
        data = filtered_data()
        location_summary = data.groupby('LocationName').agg({
            'StaffCount': 'sum',
            'JobTitle': 'nunique',
            'UnitName': 'nunique',
            'GroupName': 'nunique'
        }).reset_index()
        location_summary.columns = ['Location', 'Total Staff', 'Unique Jobs', 'Business Units', 'Business Groups']
        location_summary = location_summary.sort_values('Total Staff', ascending=False)

        return render.DataGrid(
            location_summary,
            filters=True,
            width="100%",
            height="500px"
        )

    # Data Explorer Tab Outputs
    @output
    @render.data_frame
    def data_table():
        table_choice = input.table_select()

        if table_choice == "Merged Data (All Tables Combined)":
            data = filtered_data()[['GroupName', 'UnitName', 'JobTitle', 'LocationName', 'StaffCount']]
        elif table_choice == "Business Groups":
            data = business_groups()
        elif table_choice == "Business Units":
            data = business_units().merge(business_groups(), on='GroupID', how='left')
        elif table_choice == "Job Titles":
            data = job_titles()
        elif table_choice == "Pay Locations":
            data = pay_locations()
        else:  # Staff Assignments
            data = staff_assignments()

        return render.DataGrid(
            data,
            filters=True,
            width="100%",
            height="600px",
            row_selection_mode="multiple"
        )

    @session.download
    def download_data():
        table_choice = input.table_select()

        if table_choice == "Merged Data (All Tables Combined)":
            data = filtered_data()
            filename = "merged_staff_data.csv"
        elif table_choice == "Business Groups":
            data = business_groups()
            filename = "business_groups.csv"
        elif table_choice == "Business Units":
            data = business_units().merge(business_groups(), on='GroupID', how='left')
            filename = "business_units_with_groups.csv"
        elif table_choice == "Job Titles":
            data = job_titles()
            filename = "job_titles.csv"
        elif table_choice == "Pay Locations":
            data = pay_locations()
            filename = "pay_locations.csv"
        else:  # Staff Assignments
            data = staff_assignments()
            filename = "staff_assignments.csv"

        return data.to_csv(index=False), filename

    # Insights Tab Outputs
    @output
    @render.text
    def total_staff():
        return f"{merged_data()['StaffCount'].sum():,}"

    @output
    @render.text
    def total_positions():
        return f"{len(staff_assignments()):,}"

    @output
    @render.text
    def avg_staff_unit():
        avg = merged_data().groupby('UnitName')['StaffCount'].sum().mean()
        return f"{avg:.1f}"

    @output
    @render.text
    def total_locations():
        return f"{pay_locations()['LocationName'].nunique()}"

    @output
    @render_plotly
    def concentration_chart():
        # Calculate Lorenz curve for staff concentration
        unit_totals = merged_data().groupby('UnitName')['StaffCount'].sum().sort_values()
        cumsum = unit_totals.cumsum() / unit_totals.sum()
        x = np.arange(len(unit_totals)) / len(unit_totals)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x, y=cumsum,
            mode='lines',
            name='Actual Distribution',
            line=dict(color='blue', width=3)
        ))
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1],
            mode='lines',
            name='Perfect Equality',
            line=dict(color='red', dash='dash')
        ))

        fig.update_layout(
            xaxis_title="Cumulative % of Business Units",
            yaxis_title="Cumulative % of Staff",
            showlegend=True,
            height=400,
            margin=dict(l=0, r=0, t=0, b=0)
        )
        return fig

    @output
    @render_plotly
    def group_composition():
        group_stats = merged_data().groupby('GroupName').agg({
            'StaffCount': 'sum',
            'UnitName': 'nunique',
            'JobTitle': 'nunique'
        }).reset_index()

        fig = make_subplots(
            rows=1, cols=3,
            subplot_titles=('Staff Count', 'Business Units', 'Job Titles'),
            specs=[[{'type': 'bar'}, {'type': 'bar'}, {'type': 'bar'}]]
        )

        fig.add_trace(
            go.Bar(x=group_stats['GroupName'], y=group_stats['StaffCount'], name='Staff', marker_color='lightblue'),
            row=1, col=1
        )
        fig.add_trace(
            go.Bar(x=group_stats['GroupName'], y=group_stats['UnitName'], name='Units', marker_color='lightgreen'),
            row=1, col=2
        )
        fig.add_trace(
            go.Bar(x=group_stats['GroupName'], y=group_stats['JobTitle'], name='Jobs', marker_color='lightcoral'),
            row=1, col=3
        )

        fig.update_layout(
            showlegend=False,
            height=400,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        fig.update_xaxes(tickangle=-45)
        return fig


# Create the Shiny app
app = App(app_ui, server)