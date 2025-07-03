from shiny import App, ui, render, reactive, Inputs, Outputs, Session
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# Read the CSV file
csv_path = Path(__file__).parent / "hccpositioninfo.csv"
df = pd.read_csv(csv_path, encoding='cp1252')

# Prepare data
df['Job Title'] = df['Job Title'].str.strip()
df['Group'] = df['Group'].str.strip()
df['Division'] = df['Division'].str.strip()
df['Manager Job Title'] = df['Manager Job Title'].fillna('No Manager').str.strip()

# Calculate summary statistics
total_positions = len(df)
unique_job_titles = df['Job Title'].nunique()
total_groups = df['Group'].nunique()
total_divisions = df['Division'].nunique()

# App UI
app_ui = ui.page_navbar(
    ui.nav_panel(
        "Overview",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Filters"),
                ui.input_select(
                    "filter_group",
                    "Select Group:",
                    choices=["All"] + sorted(df['Group'].unique().tolist()),
                    selected="All",
                    multiple=False
                ),
                ui.input_select(
                    "filter_division",
                    "Select Division:",
                    choices=["All"] + sorted(df['Division'].unique().tolist()),
                    selected="All",
                    multiple=False
                ),
                ui.input_select(
                    "filter_manager",
                    "Select Manager:",
                    choices=["All"] + sorted(df['Manager Job Title'].unique().tolist()),
                    selected="All",
                    multiple=False
                ),
                ui.hr(),
                ui.h5("Quick Stats"),
                ui.output_ui("quick_stats"),
                bg="#f8f9fa",
                width=300
            ),
            ui.row(
                ui.column(
                    3,
                    ui.value_box(
                        "Total Positions",
                        ui.output_text("total_positions_box"),
                        theme="primary"
                    )
                ),
                ui.column(
                    3,
                    ui.value_box(
                        "Unique Job Titles",
                        ui.output_text("unique_titles_box"),
                        theme="info"
                    )
                ),
                ui.column(
                    3,
                    ui.value_box(
                        "Groups",
                        ui.output_text("total_groups_box"),
                        theme="success"
                    )
                ),
                ui.column(
                    3,
                    ui.value_box(
                        "Divisions",
                        ui.output_text("total_divisions_box"),
                        theme="warning"
                    )
                )
            ),
            ui.hr(),
            ui.row(
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Positions by Group"),
                        ui.output_plot("group_chart", height="400px")
                    )
                ),
                ui.column(
                    6,
                    ui.card(
                        ui.card_header("Positions by Division"),
                        ui.output_plot("division_chart", height="400px")
                    )
                )
            )
        )
    ),
    ui.nav_panel(
        "Data Explorer",
        ui.card(
            ui.card_header(
                "Position Details",
                ui.download_button("download_filtered", "Download Filtered Data", class_="btn-sm float-end")
            ),
            ui.output_data_frame("position_table")
        )
    ),
    ui.nav_panel(
        "Hierarchy View",
        ui.card(
            ui.card_header("Organizational Hierarchy"),
            ui.output_plot("hierarchy_chart", height="600px")
        )
    ),
    ui.nav_panel(
        "Analytics",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h4("Analysis Options"),
                ui.input_radio_buttons(
                    "analysis_type",
                    "Select Analysis:",
                    choices={
                        "top_positions": "Top Job Positions",
                        "manager_span": "Manager Span of Control",
                        "group_division": "Group-Division Matrix"
                    },
                    selected="top_positions"
                ),
                ui.input_slider(
                    "top_n",
                    "Number of items to show:",
                    min=5,
                    max=20,
                    value=10
                ),
                bg="#f8f9fa"
            ),
            ui.card(
                ui.card_header("Analysis Results"),
                ui.output_plot("analysis_chart", height="500px")
            ),
            ui.card(
                ui.card_header("Analysis Summary"),
                ui.output_ui("analysis_summary")
            )
        )
    ),
    title="Council Positions Dashboard",
    inverse=True,
    bg="#0d6efd"
)


# Server logic
def server(input: Inputs, output: Outputs, session: Session):
    @reactive.calc
    def filtered_data():
        data = df.copy()

        if input.filter_group() != "All":
            data = data[data['Group'] == input.filter_group()]

        if input.filter_division() != "All":
            data = data[data['Division'] == input.filter_division()]

        if input.filter_manager() != "All":
            data = data[data['Manager Job Title'] == input.filter_manager()]

        return data

    @render.text
    def total_positions_box():
        return str(len(filtered_data()))

    @render.text
    def unique_titles_box():
        return str(filtered_data()['Job Title'].nunique())

    @render.text
    def total_groups_box():
        return str(filtered_data()['Group'].nunique())

    @render.text
    def total_divisions_box():
        return str(filtered_data()['Division'].nunique())

    @render.ui
    def quick_stats():
        data = filtered_data()
        return ui.div(
            ui.p(f"Filtered Positions: {len(data)}"),
            ui.p(f"Unique Titles: {data['Job Title'].nunique()}"),
            ui.p(f"Groups: {data['Group'].nunique()}"),
            ui.p(f"Divisions: {data['Division'].nunique()}")
        )

    @render.plot
    def group_chart():
        data = filtered_data()
        group_counts = data['Group'].value_counts().reset_index()
        group_counts.columns = ['Group', 'Count']

        fig = px.bar(
            group_counts,
            x='Count',
            y='Group',
            orientation='h',
            color='Count',
            color_continuous_scale='Blues',
            text='Count'
        )
        fig.update_traces(textposition='outside')
        fig.update_layout(
            showlegend=False,
            xaxis_title="Number of Positions",
            yaxis_title="",
            height=400,
            margin=dict(l=20, r=20, t=20, b=20)
        )
        return fig

    @render.plot
    def division_chart():
        data = filtered_data()
        division_counts = data['Division'].value_counts().head(10).reset_index()
        division_counts.columns = ['Division', 'Count']

        fig = px.pie(
            division_counts,
            values='Count',
            names='Division',
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(
            showlegend=True,
            height=400,
            margin=dict(l=20, r=20, t=20, b=20)
        )
        return fig

    @render.data_frame
    def position_table():
        data = filtered_data()
        return render.DataGrid(
            data,
            filters=True,
            selection_mode="rows",
            height="600px"
        )

    @render.plot
    def hierarchy_chart():
        data = filtered_data()

        # Create hierarchy data
        manager_counts = data.groupby('Manager Job Title').size().reset_index(name='Direct Reports')
        manager_counts = manager_counts[manager_counts['Manager Job Title'] != 'No Manager']
        manager_counts = manager_counts.sort_values('Direct Reports', ascending=False).head(15)

        fig = go.Figure(data=[go.Treemap(
            labels=manager_counts['Manager Job Title'],
            values=manager_counts['Direct Reports'],
            parents=[""] * len(manager_counts),
            textinfo="label+value",
            marker=dict(
                colorscale='Viridis',
                cmid=manager_counts['Direct Reports'].mean()
            )
        )])

        fig.update_layout(
            title="Top 15 Managers by Direct Reports",
            height=600,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        return fig

    @render.plot
    def analysis_chart():
        data = filtered_data()

        if input.analysis_type() == "top_positions":
            position_counts = data['Job Title'].value_counts().head(input.top_n()).reset_index()
            position_counts.columns = ['Job Title', 'Count']

            fig = px.bar(
                position_counts,
                x='Count',
                y='Job Title',
                orientation='h',
                color='Count',
                color_continuous_scale='Viridis',
                text='Count',
                title=f"Top {input.top_n()} Job Positions"
            )
            fig.update_traces(textposition='outside')

        elif input.analysis_type() == "manager_span":
            manager_span = data.groupby('Manager Job Title').size().reset_index(name='Span')
            manager_span = manager_span[manager_span['Manager Job Title'] != 'No Manager']
            manager_span = manager_span.sort_values('Span', ascending=False).head(input.top_n())

            fig = px.scatter(
                manager_span,
                x='Manager Job Title',
                y='Span',
                size='Span',
                color='Span',
                color_continuous_scale='Reds',
                title=f"Top {input.top_n()} Managers by Span of Control",
                size_max=50
            )
            fig.update_xaxis(tickangle=-45)

        else:  # group_division
            matrix_data = data.groupby(['Group', 'Division']).size().reset_index(name='Count')
            matrix_pivot = matrix_data.pivot(index='Group', columns='Division', values='Count').fillna(0)

            fig = px.imshow(
                matrix_pivot,
                labels=dict(x="Division", y="Group", color="Position Count"),
                color_continuous_scale='YlOrRd',
                title="Group-Division Position Distribution",
                aspect="auto"
            )
            fig.update_xaxis(tickangle=-45)

        fig.update_layout(
            height=500,
            margin=dict(l=20, r=20, t=40, b=80),
            showlegend=False
        )
        return fig

    @render.ui
    def analysis_summary():
        data = filtered_data()

        if input.analysis_type() == "top_positions":
            top_position = data['Job Title'].value_counts().iloc[0] if len(data) > 0 else 0
            unique_positions = data['Job Title'].nunique()
            summary = ui.div(
                ui.h5("Key Insights"),
                ui.p(f"Most common position: {data['Job Title'].value_counts().index[0] if len(data) > 0 else 'N/A'}"),
                ui.p(f"Number of staff in top position: {top_position}"),
                ui.p(f"Total unique positions: {unique_positions}"),
                ui.p(
                    f"Average staff per position: {len(data) / unique_positions:.1f}" if unique_positions > 0 else "N/A")
            )

        elif input.analysis_type() == "manager_span":
            manager_stats = data[data['Manager Job Title'] != 'No Manager'].groupby('Manager Job Title').size()
            if len(manager_stats) > 0:
                summary = ui.div(
                    ui.h5("Manager Statistics"),
                    ui.p(f"Total managers: {len(manager_stats)}"),
                    ui.p(f"Average span of control: {manager_stats.mean():.1f}"),
                    ui.p(f"Maximum span: {manager_stats.max()}"),
                    ui.p(f"Minimum span: {manager_stats.min()}")
                )
            else:
                summary = ui.p("No manager data available")

        else:  # group_division
            summary = ui.div(
                ui.h5("Matrix Overview"),
                ui.p(f"Total groups: {data['Group'].nunique()}"),
                ui.p(f"Total divisions: {data['Division'].nunique()}"),
                ui.p(f"Most populated group: {data['Group'].value_counts().index[0] if len(data) > 0 else 'N/A'}"),
                ui.p(f"Most populated division: {data['Division'].value_counts().index[0] if len(data) > 0 else 'N/A'}")
            )

        return summary

    @session.download(filename=lambda: f"filtered_positions_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv")
    def download_filtered():
        return filtered_data().to_csv(index=False)


# Create app
app = App(app_ui, server)