"""
Plot parameter analysis: For each experiment parameter, plot it against revenue.
Reads CSV file and creates individual plots for each parameter.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# The 10 parameters that were varied in the experiment
PARAMETERS = [
    'num_cashiers',
    'num_packers',
    'num_cooks',
    'num_bussers',
    'pickup_shelf_capacity',
    'coffee_urn_size',
    'num_espresso_machines',
    'num_coffee_urns',
    'brew_time',
    'priority_packing'
]

REVENUE_COLUMN = 'total_profit'  # Using total_profit as revenue metric


def derive_order_complete_percentage(csv_file):
    """Derive order completion percentage if not already present."""
    df = read_and_process_csv(csv_file)
    if 'order_complete_percentage' not in df.columns and \
       'throughput_total' in df.columns and 'arrival_total' in df.columns:
        df['order_complete_percentage'] = df.apply(
            lambda row: (row['throughput_total'] / row['arrival_total'])
            if pd.notna(row['arrival_total']) and row['arrival_total'] != 0 else 0,
            axis=1
        )
    df.to_csv(csv_file, index=False)
    return df


def read_and_process_csv(csv_file):
    """Read CSV and prepare data for plotting."""
    df = pd.read_csv(csv_file)
    return df


def plot_parameter_vs_revenue(df, param_name, revenue_col=REVENUE_COLUMN, output_dir='plots'):
    """
    Plot a single parameter against revenue using box plots.
    Shows distribution of revenue values across replications for each parameter value.
    """
    # Check if parameter exists in dataframe
    if param_name not in df.columns:
        print(f"Warning: Parameter '{param_name}' not found in CSV. Skipping.")
        return
    
    # Group by parameter value and collect all revenue values (not just aggregated stats)
    grouped_data = []
    param_values = []
    
    # Get unique parameter values - include NaN/None values
    unique_params = df[param_name].unique()
    
    # Handle sorting: separate NaN and non-NaN values
    nan_present = pd.isna(unique_params).any()
    non_nan_params = [p for p in unique_params if pd.notna(p)]
    
    # Sort non-NaN values if numeric
    if df[param_name].dtype in [np.int64, np.float64]:
        non_nan_params = sorted(non_nan_params)
    
    # Build the list: put None/NaN first if present, then sorted non-NaN values
    if nan_present:
        unique_params_list = [None] + non_nan_params
    else:
        unique_params_list = non_nan_params
    
    # Collect revenue data for each parameter value
    for param_val in unique_params_list:
        # Handle NaN comparison properly
        if pd.isna(param_val):
            revenue_values = df[df[param_name].isna()][revenue_col].dropna().tolist()
        else:
            revenue_values = df[df[param_name] == param_val][revenue_col].dropna().tolist()
        
        if len(revenue_values) > 0:
            grouped_data.append(revenue_values)
            param_values.append(param_val)
    
    if len(grouped_data) == 0:
        print(f"Warning: No data found for parameter '{param_name}'. Skipping.")
        return
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create labels, handling None/NaN properly
    labels = []
    for x in param_values:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            labels.append('FIFO')
        else:
            labels.append(str(x))
    
    # Create box plot (labels -> tick_labels to avoid deprecation)
    bp = ax.boxplot(
        grouped_data,
        tick_labels=labels,
        patch_artist=True,
        showmeans=True,
        meanline=True
    )
    
    # Style the box plots
    for patch in bp['boxes']:
        patch.set_facecolor('steelblue')
        patch.set_alpha(0.7)
        patch.set_edgecolor('black')
        patch.set_linewidth(1.5)
    
    # Style other elements
    for element in ['whiskers', 'fliers', 'medians', 'caps']:
        plt.setp(bp[element], color='black', linewidth=1.5)
    
    # Style means
    plt.setp(bp['means'], color='red', linewidth=2, linestyle='--')
    
    # Rotate x-axis labels if needed
    if param_name == 'priority_packing' or len(param_values) > 5:
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # Add legend explaining box plot components
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='steelblue', lw=8, alpha=0.7, label='Box: Interquartile Range (25%-75%)'),
        Line2D([0], [0], color='black', lw=2, label='Line in Box: Median (50%)'),
        Line2D([0], [0], color='red', linestyle='--', lw=2, label='Red Dashed Line: Mean'),
        Line2D([0], [0], color='black', lw=1.5, label='Whiskers: Min/Max'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='black', 
               markersize=6, linestyle='None', label='Outliers')
    ]
    ax.legend(
        handles=legend_elements,
        loc='upper left',
        bbox_to_anchor=(1.02, 1),
        borderaxespad=0,
        fontsize=9,
        framealpha=0.9
    )
    
    # Add text annotation explaining what the data shows
    rep_counts = df.groupby(param_name)[revenue_col].count()
    min_reps = rep_counts.min()
    max_reps = rep_counts.max()
    if min_reps == max_reps:
        info_text = f"Each box shows revenue distribution across {min_reps:.0f} replications"
    else:
        info_text = f"Each box shows revenue distribution across {min_reps:.0f}-{max_reps:.0f} replications"
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes, 
            fontsize=9, verticalalignment='top', 
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Labels and title
    ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12, fontweight='bold')
    ax.set_ylabel('Revenue (Total Profit)', fontsize=12, fontweight='bold')
    ax.set_title(f'Revenue vs {param_name.replace("_", " ").title()}', 
                fontsize=14, fontweight='bold', pad=20)
    
    # Format y-axis to show currency-like format
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    plt.tight_layout()
    
    # Save figure
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    filename = f'{param_name}_vs_revenue.png'
    filepath = output_path / filename
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    print(f"Saved: {filepath}")
    
    plt.close()


def create_all_plots(csv_file, output_dir='plots'):
    """Create plots for all parameters."""
    # print(f"Reading CSV file: {csv_file}")
    df = read_and_process_csv(csv_file)
    
    # print(f"Loaded {len(df)} rows")
    # print(f"Found {df['scenario_id'].nunique()} unique scenarios")
    # print(f"Found {df['replication'].nunique()} replications per scenario")
    
    # Find which parameters are actually in the CSV
    available_params = [p for p in PARAMETERS if p in df.columns]
    missing_params = [p for p in PARAMETERS if p not in df.columns]
    
    if missing_params:
        print(f"\nNote: The following parameters were not found in CSV: {missing_params}")
    
    print(f"\nCreating plots for {len(available_params)} available parameters...")
    print("=" * 60)
    
    # Create plots for each available parameter
    for param in available_params:
        # print(f"Plotting: {param}")
        plot_parameter_vs_revenue(df, param, revenue_col='total_profit', output_dir=output_dir)
    
    print("=" * 60)
    print(f"All plots saved to '{output_dir}' directory")


def create_summary_statistics(csv_file):
    """Print summary statistics about the data."""
    df = read_and_process_csv(csv_file)
    
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)
    print(f"Total rows: {len(df)}")
    print(f"Unique scenarios: {df['scenario_id'].nunique()}")
    print(f"Replications per scenario: {df.groupby('scenario_id')['replication'].count().iloc[0]}")
    print(f"\nRevenue Statistics:")
    print(f"  Mean: ${df[REVENUE_COLUMN].mean():,.2f}")
    print(f"  Std:  ${df[REVENUE_COLUMN].std():,.2f}")
    print(f"  Min:  ${df[REVENUE_COLUMN].min():,.2f}")
    print(f"  Max:  ${df[REVENUE_COLUMN].max():,.2f}")
    
    print(f"\nParameter Ranges (available in CSV):")
    available_params = [p for p in PARAMETERS if p in df.columns]
    for param in available_params:
        unique_vals = df[param].unique()
        if len(unique_vals) > 0:
            # Sort if numeric, otherwise keep original order
            try:
                sorted_vals = sorted([v for v in unique_vals if pd.notna(v)])
            except TypeError:
                sorted_vals = [v for v in unique_vals if pd.notna(v)]
            print(f"  {param}: {sorted_vals}")
    print("=" * 60 + "\n")


def scenario_mean_by_param(csv_file, param_name, value_col=REVENUE_COLUMN, scenario_ids=None):
    """
    Calculate mean of a target column for each scenario, grouped by a parameter value.
    Optionally filter to a given list of scenario_ids.
    
    Returns: DataFrame with scenario_id, parameter value, and mean of the value_col.
    """
    df = read_and_process_csv(csv_file)
    if param_name not in df.columns:
        raise ValueError(f"Parameter '{param_name}' not found in data.")
    if value_col not in df.columns:
        raise ValueError(f"Value column '{value_col}' not found in data.")

    data = df
    if scenario_ids is not None:
        data = data[data['scenario_id'].isin(scenario_ids)]

    grouped = (
        data.groupby(['scenario_id', param_name])[value_col]
        .mean()
        .reset_index()
        .rename(columns={value_col: f"{value_col}_mean"})
    )
    return grouped


def plot_scenario_mean_by_param(csv_file, param_name, value_col=REVENUE_COLUMN, scenario_ids=None, output_dir='plots'):
    """
    Plot mean of a target column for each scenario, grouped by a parameter value.
    Optionally filter to a given list of scenario_ids.
    """
    means_df = scenario_mean_by_param(csv_file, param_name, value_col=value_col, scenario_ids=scenario_ids)

    if means_df.empty:
        print(f"No data to plot for param '{param_name}' with given scenario filter.")
        return

    # Figure setup
    fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")

    # Determine plotting strategy based on param type (scatter for both)
    is_numeric = pd.api.types.is_numeric_dtype(means_df[param_name])

    # One color per scenario_id
    scenario_ids_unique = means_df['scenario_id'].unique()
    colors = plt.cm.tab10.colors

    if is_numeric:
        # Numeric param: scatter x=param, y=mean value, colored by scenario
        for idx, scenario in enumerate(sorted(scenario_ids_unique)):
            subset = means_df[means_df['scenario_id'] == scenario]
            color = colors[idx % len(colors)]
            ax.scatter(
                subset[param_name],
                subset[f"{value_col}_mean"],
                label=f"Scenario {scenario}",
                color=color,
                s=40,
                alpha=0.8,
                edgecolors='black',
                linewidths=0.5,
            )
        ax.grid(True, linestyle='--', alpha=0.3)
    else:
        # Categorical param: map categories to positions and scatter with jitter per scenario
        categories = list(dict.fromkeys(means_df[param_name].tolist()))  # preserve order
        x_pos = {cat: i for i, cat in enumerate(categories)}
        jitter = 0.08
        for idx, scenario in enumerate(sorted(scenario_ids_unique)):
            subset = means_df[means_df['scenario_id'] == scenario]
            color = colors[idx % len(colors)]
            xs = [x_pos[val] + (idx - len(scenario_ids_unique)/2)*jitter for val in subset[param_name]]
            ax.scatter(
                xs,
                subset[f"{value_col}_mean"],
                label=f"Scenario {scenario}",
                color=color,
                s=40,
                alpha=0.8,
                edgecolors='black',
                linewidths=0.5,
            )
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels([str(v) for v in categories], rotation=45, ha='right')
        ax.grid(True, linestyle='--', alpha=0.3, axis='y')

    ax.set_xlabel(param_name.replace('_', ' ').title(), fontsize=12, fontweight='bold')
    ax.set_ylabel(f"Mean {value_col.replace('_', ' ').title()}", fontsize=12, fontweight='bold')
    ax.set_title(f"Scenario Mean of {value_col.replace('_', ' ').title()} by {param_name.replace('_', ' ').title()}",
                 fontsize=14, fontweight='bold', pad=20)

    ax.legend(title="Scenario", fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Save figure
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    filename = f"scenario_mean_{param_name}.png"
    filepath = output_path / filename
    plt.savefig(filepath, dpi=150)
    print(f"Saved: {filepath}")

    plt.close()

if __name__ == "__main__":
    import sys
    
    # Default CSV file
    csv_file = 'experiment_results_v6.csv'
    
    # Allow command line argument for CSV file
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    # Check if file exists
    if not Path(csv_file).exists():
        print(f"Error: CSV file '{csv_file}' not found!")
        print(f"Usage: python plot_parameter_analysis.py [csv_file]")
        sys.exit(1)
    
    # Print summary
    # create_summary_statistics(csv_file)
    
    # # Create all plots
    # create_all_plots(csv_file)
    
    # Scenario-mean scatter example: change param_name as needed
    # derive_order_complete_percentage(csv_file)
    scenario_ids = [11132,15019,7341,15022,11203]
    plot_scenario_mean_by_param(csv_file, 'order_complete_percentage', value_col='total_profit', scenario_ids=scenario_ids, output_dir='plots')

    print("\nDone! Check the 'plots' directory for all generated plots.")

