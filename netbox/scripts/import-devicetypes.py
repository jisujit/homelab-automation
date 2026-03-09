import os
import yaml
import pynetbox

# NetBox connection
nb = pynetbox.api(
    'http://localhost:8000',
    token='nbt_vpTnx5y7y0HH.JbBMAzfSiXJc75BhkJ90M77AzG7GrcbfJELNLyWC'
)

# Manufacturers we want to import
MANUFACTURERS = [
    'HPE',
]

library_path = '/opt/devicetype-library/device-types'

imported = 0
skipped = 0
errors = 0

for manufacturer in MANUFACTURERS:
    mfr_path = os.path.join(library_path, manufacturer)
    if not os.path.exists(mfr_path):
        print(f"⚠️  Manufacturer directory not found: {manufacturer}")
        continue

    # Create manufacturer if it doesn't exist
    mfr_obj = nb.dcim.manufacturers.get(name=manufacturer)
    if not mfr_obj:
        mfr_obj = nb.dcim.manufacturers.create(
            name=manufacturer,
            slug=manufacturer.lower().replace(' ', '-')
        )
        print(f"✅ Created manufacturer: {manufacturer}")

    # Import device types
    for filename in os.listdir(mfr_path):
        if not filename.endswith('.yaml'):
            continue
        filepath = os.path.join(mfr_path, filename)
        with open(filepath, 'r') as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                print(f"❌ YAML error in {filename}: {e}")
                errors += 1
                continue

        # Check if device type already exists
        existing = nb.dcim.device_types.get(
            manufacturer_id=mfr_obj.id,
            model=data.get('model')
        )
        if existing:
            skipped += 1
            continue

        try:
            nb.dcim.device_types.create(
                manufacturer=mfr_obj.id,
                model=data.get('model'),
                slug=data.get('slug'),
                u_height=data.get('u_height', 1),
                is_full_depth=data.get('is_full_depth', True),
            )
            print(f"  ✅ Imported: {data.get('model')}")
            imported += 1
        except Exception as e:
            print(f"  ❌ Error importing {data.get('model')}: {e}")
            errors += 1

print(f"\n📊 Summary: {imported} imported, {skipped} skipped, {errors} errors")
