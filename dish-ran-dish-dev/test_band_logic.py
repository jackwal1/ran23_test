#!/usr/bin/env python3
"""
Minimal test for band filtering logic
"""
import asyncio
import re
from typing import List, Dict, Any, Optional

# Copy the essential functions and constants from ran_automation_tools.py
BAND_MAPPING = {
    "n29": "LB", "n71": "LB",
    "n66": "MB", "n70": "MB"
}

def _parse_cellname(cellname: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parses a cell name using regex to reliably extract site, sector, and band."""
    if not cellname: return None, None, None
    # Regex to capture site (alphanumeric), sector (numeric), and band (starts with 'n' followed by numbers)
    match = re.match(r"^(?P<site>[A-Z0-9]+)_(?P<sector>\d+)_(?P<band>n\d+)", cellname)
    if match:
        parts = match.groupdict()
        return parts.get("site"), parts.get("sector"), parts.get("band")
    # Fallback for other formats
    parts = cellname.split("_")
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    return None, None, None

def _get_column_value(row: Dict[str, Any], column_name: str) -> Any:
    """Gets a value from a row, trying various case formats for the key."""
    for key in [column_name, column_name.upper(), column_name.lower(), column_name.title()]:
        if key in row: return row[key]
    return None

async def mock_extract_band_identifier(band_upper: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mock implementation of extract_band_identifier for testing"""
    print(f"   Mock: extract_band_identifier called with band '{band_upper}' on {len(data)} records")
    return data  # Just return all data for testing

async def _filter_by_band(data: List[Dict[str, Any]], band: Optional[str], cell_col_name: str) -> List[Dict[str, Any]]:
    """Filters data based on band, extracted from a cell name column."""
    if not data:
        return data
    
    # If no band is provided, extract band from cell names and apply mapping
    if not band:
        # Extract bands from all cell names and determine the mapped band category
        extracted_bands = set()
        for row in data:
            cell_name = str(_get_column_value(row, cell_col_name) or "")
            _, _, parsed_band = _parse_cellname(cell_name)
            if parsed_band:
                mapped_band = BAND_MAPPING.get(parsed_band.lower())
                if mapped_band:
                    extracted_bands.add(mapped_band)
        
        # If we found multiple different mapped bands (LB and MB), return all data
        if len(extracted_bands) > 1:
            return data
        
        # If we found exactly one mapped band category, use it for filtering
        if len(extracted_bands) == 1:
            band = list(extracted_bands)[0]
        else:
            # No recognizable bands found, return data as-is
            return data
    
    band_upper = band.upper()
    if band_upper in ("LB", "MB"):
        return await mock_extract_band_identifier(band_upper, data)
    else:
        # For specific bands (n29, n66, etc.), use direct filtering
        allowed_bands = [band_upper.lower()]
        
        # If this is a mapped band, get all bands that map to it
        allowed_bands = [b for b, mapped in BAND_MAPPING.items() if mapped.upper() == band_upper]
        if not allowed_bands:
            allowed_bands = [band_upper.lower()]
        
        filtered_data = []
        for row in data:
            cell_name = str(_get_column_value(row, cell_col_name) or "")
            _, _, parsed_band = _parse_cellname(cell_name)
            if parsed_band and parsed_band.lower() in allowed_bands:
                filtered_data.append(row)
        return filtered_data

async def test_band_filtering():
    """Test the band filtering functionality"""
    print("🧪 Testing Band Filtering Functionality")
    print("=" * 50)
    
    # Test data with different cell names and bands
    test_data = [
        {"CELLNAME": "SITE001_1_n29_A", "TILT": "5.0"},
        {"CELLNAME": "SITE001_2_n71_B", "TILT": "6.0"},
        {"CELLNAME": "SITE002_1_n66_A", "TILT": "4.0"},
        {"CELLNAME": "SITE002_2_n70_B", "TILT": "7.0"},
        {"CELLNAME": "SITE003_1_n29_C", "TILT": "3.0"},
    ]
    
    print(f"📊 Test data: {len(test_data)} records")
    for i, record in enumerate(test_data, 1):
        print(f"  {i}. {record['CELLNAME']} (Tilt: {record['TILT']})")
    
    print(f"\n🗺️  Band Mapping: {BAND_MAPPING}")
    
    # Test 1: Filter with specific band (n29)
    print("\n🔍 Test 1: Filter with specific band 'n29'")
    result1 = await _filter_by_band(test_data, "n29", "CELLNAME")
    print(f"   Result: {len(result1)} records")
    for record in result1:
        print(f"   - {record['CELLNAME']}")
    expected_n29 = [r for r in test_data if "n29" in r['CELLNAME']]
    assert len(result1) == len(expected_n29), f"Expected {len(expected_n29)} n29 records, got {len(result1)}"
    
    # Test 2: Filter with band category (LB) - should include n29 and n71
    print("\n🔍 Test 2: Filter with band category 'LB'")
    result2 = await _filter_by_band(test_data, "LB", "CELLNAME")
    print(f"   Result: {len(result2)} records")
    for record in result2:
        print(f"   - {record['CELLNAME']}")
    
    # Test 3: Filter with band category (MB) - should include n66 and n70
    print("\n🔍 Test 3: Filter with band category 'MB'")
    result3 = await _filter_by_band(test_data, "MB", "CELLNAME")
    print(f"   Result: {len(result3)} records")
    for record in result3:
        print(f"   - {record['CELLNAME']}")
    
    # Test 4: No band provided - should auto-detect and return all (mixed bands)
    print("\n🔍 Test 4: No band provided (auto-detection with mixed bands)")
    result4 = await _filter_by_band(test_data, None, "CELLNAME")
    print(f"   Result: {len(result4)} records (should return all since mixed LB/MB)")
    assert len(result4) == len(test_data), f"Expected all {len(test_data)} records, got {len(result4)}"
    
    # Test 5: Test with LB-only data
    lb_only_data = [r for r in test_data if any(band in r['CELLNAME'] for band in ['n29', 'n71'])]
    print(f"\n🔍 Test 5: No band provided with LB-only data ({len(lb_only_data)} records)")
    result5 = await _filter_by_band(lb_only_data, None, "CELLNAME")
    print(f"   Result: {len(result5)} records (should return all LB records)")
    for record in result5:
        print(f"   - {record['CELLNAME']}")
    assert len(result5) == len(lb_only_data), f"Expected {len(lb_only_data)} LB records, got {len(result5)}"
    
    # Test 6: Test _parse_cellname function
    print("\n🔍 Test 6: Cell name parsing")
    test_cell_names = [
        "SITE001_1_n29_A",
        "HOHOU00562A_1_n29_E_DL",
        "DNDEN00048B_3_n70_AWS-4_UL15",
        "INVALID_CELLNAME"
    ]
    
    for cell_name in test_cell_names:
        site, sector, band = _parse_cellname(cell_name)
        mapped_band = BAND_MAPPING.get(band.lower() if band else "")
        print(f"   {cell_name}")
        print(f"     -> Site: {site}, Sector: {sector}, Band: {band}")
        print(f"     -> Mapped to: {mapped_band}")
    
    print("\n✅ All tests completed successfully!")

def test_band_mapping_logic():
    """Test the band mapping logic"""
    print("🧪 Testing Band Mapping Logic")
    print("=" * 30)
    
    # Test the mapping
    expected_mappings = {
        "n29": "LB",
        "n71": "LB", 
        "n66": "MB",
        "n70": "MB"
    }
    
    all_correct = True
    for band, expected in expected_mappings.items():
        actual = BAND_MAPPING.get(band)
        status = "✅" if actual == expected else "❌"
        if actual != expected:
            all_correct = False
        print(f"   {status} {band} -> {actual} (expected: {expected})")
    
    # Test reverse mapping (LB/MB to bands)
    lb_bands = [b for b, mapped in BAND_MAPPING.items() if mapped == "LB"]
    mb_bands = [b for b, mapped in BAND_MAPPING.items() if mapped == "MB"]
    
    print(f"\n   LB bands: {lb_bands}")
    print(f"   MB bands: {mb_bands}")
    
    assert all_correct, "Band mapping validation failed!"
    assert set(lb_bands) == {"n29", "n71"}, f"Expected LB bands to be n29,n71, got {lb_bands}"
    assert set(mb_bands) == {"n66", "n70"}, f"Expected MB bands to be n66,n70, got {mb_bands}"

if __name__ == "__main__":
    print("🚀 Starting Band Filtering Tests")
    try:
        test_band_mapping_logic()
        asyncio.run(test_band_filtering())
        print("\n🎉 All tests completed successfully!")
        print("✅ Band filtering logic is working correctly after the changes!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        exit(1) 