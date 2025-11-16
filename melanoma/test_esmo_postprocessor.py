"""Test script for ESMO postprocessor"""

import asyncio
import sys
from pathlib import Path

# Add src to path
melanoma_dir = Path(__file__).parent
sys.path.insert(0, str(melanoma_dir / "src"))

from domain.models import ConferenceType, PostprocessingConfiguration
from app.postprocessing_service import PostprocessingService


async def test_year(year):
    """Test the ESMO postprocessor on a specific year"""
    melanoma_dir = Path(__file__).parent
    input_file = melanoma_dir / f"data/processed/ESMO_Abstracts/ESMO_{year}_marker.md"
    output_file = melanoma_dir / f"data/postprocessed/ESMO_Abstracts/ESMO_{year}.md"
    
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    if not input_file.exists():
        print(f"⚠️  Input file not found: {input_file}")
        return None
    
    print(f"\n{'='*80}")
    print(f"Testing ESMO {year}")
    print(f"{'='*80}")
    print(f"📄 Processing: {input_file}")
    print(f"💾 Output: {output_file}")
    
    # Create configuration
    config = PostprocessingConfiguration(
        conference_type=ConferenceType.ESMO,
        include_authors=False,
        preserve_tables=True,
        expand_abbreviations=False,
        standardize_terminology=False,
    )
    
    # Create service and process
    service = PostprocessingService()
    
    try:
        result = await service.process_file(
            str(input_file),
            str(output_file),
            config
        )
        
        print(f"\n✅ Processing complete!")
        print(f"   Abstracts processed: {result.abstracts_processed}")
        print(f"   Abstracts with warnings: {result.abstracts_with_warnings}")
        print(f"   Structured metadata: {result.structured_metadata_count}")
        print(f"   Conference features: {result.conference_specific_features}")
        
        if result.errors:
            print(f"\n⚠️  Errors encountered:")
            for error in result.errors:
                print(f"   - {error}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Test the ESMO postprocessor on all years"""
    years = [2020, 2021, 2022, 2023, 2024]
    results = []
    
    for year in years:
        result = await test_year(year)
        if result:
            results.append((year, result))
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    for year, result in results:
        print(f"ESMO {year}: {result.abstracts_processed} abstracts, {result.abstracts_with_warnings} warnings")
    
    # Check specific abstracts
    print(f"\n{'='*80}")
    print("Verifying specific abstracts mentioned by user:")
    print(f"{'='*80}")
    
    import re
    test_cases = [
        ('data/postprocessed/ESMO_Abstracts/ESMO_2021.md', '1040O', 'Methods'),
        ('data/postprocessed/ESMO_Abstracts/ESMO_2022.md', '800P', 'Background'),
        ('data/postprocessed/ESMO_Abstracts/ESMO_2023.md', '1093P', 'Conclusions'),
    ]
    
    all_ok = True
    for file_path, abstract_id, expected_section in test_cases:
        file = Path(__file__).parent / file_path
        if not file.exists():
            print(f"⚠️  {file_path} not found")
            all_ok = False
            continue
        
        content = file.read_text(encoding='utf-8')
        abstract_match = re.search(rf'### Abstract ID: {re.escape(abstract_id)}\n(.*?)(?=\n### Abstract ID:|\Z)', content, re.DOTALL)
        
        if abstract_match:
            abstract_text = abstract_match.group(1)
            sections = re.findall(r'#### ([^:]+):', abstract_text)
            
            if expected_section in sections:
                print(f"✅ {file_path} - Abstract {abstract_id}: {expected_section} section is present")
            else:
                print(f"❌ {file_path} - Abstract {abstract_id}: {expected_section} section is MISSING")
                print(f"   Available sections: {sections}")
                all_ok = False
        else:
            print(f"⚠️  {file_path} - Abstract {abstract_id} not found")
            all_ok = False
    
    if all_ok:
        print(f"\n✅ All sections verified!")
        return 0
    else:
        print(f"\n⚠️  Some sections are missing - need to investigate")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
