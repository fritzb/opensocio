"""
Austin 311 Public Data - Download and Analysis Script
======================================================
Data Source: City of Austin Open Data Portal
API: Socrata SODA API
Dataset ID: xwdj-i9he
URL: https://data.austintexas.gov/Utilities-and-City-Services/Austin-311-Public-Data/xwdj-i9he

Schema Reference (based on Austin 311 Open Data documentation):
- service_request_id: Unique identifier for each service request
- sr_type_desc: Service request type description (complaint category)
- sr_description: Detailed description of the service request
- owning_department: Department responsible for handling the request
- method_received: How the request was received (phone, web, app, etc.)
- sr_status: Current status of the request
- status_date: Date of the status
- created_date: Date when the request was created
- sr_location: Location information
- street_address: Street address of the incident
- city: City
- state: State
- zip_code: ZIP code
- county: County
- latitude: Latitude coordinate
- longitude: Longitude coordinate
- council_district: Austin City Council District
"""

import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import os

# ============================================================
# CONFIGURATION
# ============================================================

# API endpoint for Austin 311 Public Data
BASE_URL = "https://data.austintexas.gov/resource/xwdj-i9he.json"

# Socrata API supports up to 50,000 records per request
# Note: No API key required for public data, but rate limits apply

# ============================================================
# DATA DOWNLOAD FUNCTIONS
# ============================================================

def download_311_data(limit=10000, offset=0, order="sr_created_date DESC", where_clause=None):
    """
    Download Austin 311 data from the Socrata API.
    
    Parameters:
    -----------
    limit : int
        Number of records to fetch (max 50,000 per request)
    offset : int  
        Starting record offset for pagination
    order : str
        Sort order (e.g., "created_date DESC")
    where_clause : str
        Optional SoQL WHERE clause for filtering
        
    Returns:
    --------
    list : JSON data as list of dictionaries
    """
    params = {
        "$limit": limit,
        "$offset": offset,
        "$order": order
    }
    
    if where_clause:
        params["$where"] = where_clause
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []


def download_all_data(max_records=None, batch_size=50000):
    """
    Download all available 311 data using pagination.
    
    Parameters:
    -----------
    max_records : int or None
        Maximum records to download (None for all)
    batch_size : int
        Records per API call (max 50000)
    
    Returns:
    --------
    pandas.DataFrame : All downloaded data
    """
    all_data = []
    offset = 0
    
    print("Downloading Austin 311 data...")
    
    while True:
        batch = download_311_data(limit=batch_size, offset=offset)
        
        if not batch:
            break
            
        all_data.extend(batch)
        print(f"  Downloaded {len(all_data):,} records...")
        
        if max_records and len(all_data) >= max_records:
            all_data = all_data[:max_records]
            break
            
        if len(batch) < batch_size:
            break
            
        offset += batch_size
    
    print(f"Total records downloaded: {len(all_data):,}")
    return pd.DataFrame(all_data)


def download_recent_data(days=30):
    """
    Download data from the last N days.
    
    Parameters:
    -----------
    days : int
        Number of days to look back
    
    Returns:
    --------
    pandas.DataFrame : Recent data
    """
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    where_clause = f"sr_created_date >= '{cutoff_date}'"
    
    print(f"Downloading data from the last {days} days...")
    data = download_311_data(limit=50000, where_clause=where_clause)
    return pd.DataFrame(data)


def download_by_complaint_type(complaint_type):
    """
    Download data for a specific complaint type.
    
    Parameters:
    -----------
    complaint_type : str
        Complaint type to search for (partial match)
    
    Returns:
    --------
    pandas.DataFrame : Filtered data
    """
    where_clause = f"sr_type_desc like '%{complaint_type}%'"
    data = download_311_data(limit=50000, where_clause=where_clause)
    return pd.DataFrame(data)


# ============================================================
# ANALYSIS FUNCTIONS
# ============================================================

def analyze_schema(df):
    """Display schema information about the dataset."""
    print("\n" + "="*60)
    print("SCHEMA OVERVIEW")
    print("="*60)
    print(f"\nTotal columns: {len(df.columns)}")
    print(f"Total records: {len(df):,}")
    
    print("\n" + "-"*60)
    print("COLUMNS AND DATA TYPES:")
    print("-"*60)
    
    for col in df.columns:
        non_null = df[col].notna().sum()
        sample = df[col].dropna().iloc[0] if non_null > 0 else "N/A"

        # Skip columns with unhashable types (e.g., dicts)
        try:
            unique = df[col].nunique()
        except TypeError:
            unique = "N/A (complex type)"

        if isinstance(sample, str) and len(sample) > 50:
            sample = sample[:50] + "..."
        elif isinstance(sample, dict):
            sample = str(sample)[:50] + "..."

        print(f"\n{col}")
        print(f"  Type: {df[col].dtype}")
        print(f"  Non-null: {non_null:,} / {len(df):,} ({100*non_null/len(df):.1f}%)")
        print(f"  Unique values: {unique}")
        print(f"  Sample: {sample}")


def analyze_complaints(df):
    """Analyze complaint types and distributions."""
    print("\n" + "="*60)
    print("COMPLAINT TYPE ANALYSIS")
    print("="*60)
    
    if 'sr_type_desc' in df.columns:
        print("\nTop 25 Complaint Types:")
        print("-"*40)
        complaint_counts = df['sr_type_desc'].value_counts().head(25)
        for i, (complaint, count) in enumerate(complaint_counts.items(), 1):
            pct = 100 * count / len(df)
            print(f"{i:2}. {complaint}: {count:,} ({pct:.1f}%)")
    
    if 'sr_department_desc' in df.columns:
        print("\n\nComplaints by Department:")
        print("-"*40)
        dept_counts = df['sr_department_desc'].value_counts().head(15)
        for dept, count in dept_counts.items():
            pct = 100 * count / len(df)
            print(f"  {dept}: {count:,} ({pct:.1f}%)")


def analyze_temporal(df):
    """Analyze temporal patterns in the data."""
    print("\n" + "="*60)
    print("TEMPORAL ANALYSIS")
    print("="*60)
    
    if 'sr_created_date' in df.columns:
        df['sr_created_date'] = pd.to_datetime(df['sr_created_date'], errors='coerce')

        # Date range
        min_date = df['sr_created_date'].min()
        max_date = df['sr_created_date'].max()
        print(f"\nDate Range: {min_date} to {max_date}")

        # Monthly trends
        df['year_month'] = df['sr_created_date'].dt.to_period('M')
        monthly = df.groupby('year_month').size()
        
        print("\nMonthly Request Counts (last 12 months):")
        print("-"*40)
        for period, count in monthly.tail(12).items():
            print(f"  {period}: {count:,}")


def analyze_geographic(df):
    """Analyze geographic distribution."""
    print("\n" + "="*60)
    print("GEOGRAPHIC ANALYSIS")
    print("="*60)
    
    if 'sr_location_zip_code' in df.columns:
        print("\nTop 15 ZIP Codes by Request Count:")
        print("-"*40)
        zip_counts = df['sr_location_zip_code'].value_counts().head(15)
        for zip_code, count in zip_counts.items():
            pct = 100 * count / len(df)
            print(f"  {zip_code}: {count:,} ({pct:.1f}%)")
    
    if 'sr_location_county' in df.columns:
        print("\n\nRequests by County:")
        print("-"*40)
        county_counts = df['sr_location_county'].value_counts()
        for county, count in county_counts.items():
            if pd.notna(county):
                pct = 100 * count / len(df)
                print(f"  {county}: {count:,} ({pct:.1f}%)")


def analyze_status(df):
    """Analyze request status distribution."""
    print("\n" + "="*60)
    print("STATUS ANALYSIS")
    print("="*60)
    
    if 'sr_status_desc' in df.columns:
        print("\nRequest Status Distribution:")
        print("-"*40)
        status_counts = df['sr_status_desc'].value_counts()
        for status, count in status_counts.items():
            pct = 100 * count / len(df)
            print(f"  {status}: {count:,} ({pct:.1f}%)")

    if 'sr_method_received_desc' in df.columns:
        print("\n\nMethod of Submission:")
        print("-"*40)
        method_counts = df['sr_method_received_desc'].value_counts()
        for method, count in method_counts.items():
            pct = 100 * count / len(df)
            print(f"  {method}: {count:,} ({pct:.1f}%)")


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    # Download sample data (10,000 most recent records)
    print("="*60)
    print("AUSTIN 311 PUBLIC DATA - DOWNLOAD & ANALYSIS")
    print("="*60)
    print("\nAPI Endpoint:", BASE_URL)
    print("Data Source: City of Austin Open Data Portal")
    print("\nNote: This script downloads data from the Socrata API.")
    print("If running locally, ensure you have network access to:")
    print("  - data.austintexas.gov")
    
    # Download data
    df = download_all_data(max_records=50000)
    
    if len(df) > 0:
        # Save to CSV
        output_file = "austin_311_data.csv"
        df.to_csv(output_file, index=False)
        print(f"\nData saved to: {output_file}")
        
        # Run analyses
        analyze_schema(df)
        analyze_complaints(df)
        analyze_temporal(df)
        analyze_geographic(df)
        analyze_status(df)
        
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        
    else:
        print("\nNo data downloaded. Check network connection and API availability.")
        print("\nAlternative: Download manually from:")
        print("  https://data.austintexas.gov/Utilities-and-City-Services/Austin-311-Public-Data/xwdj-i9he")
        print("\n  Click 'Export' button and select CSV format.")

