import django, os, sys, json
sys.path.insert(0, 'src')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uu_backend.django_api.settings')
django.setup()
from uu_backend.django_data.models import GroundTruthAnnotationModel

# Show all ground truth annotations for the document
doc_id = 'ff5eb02d-bc4a-46cb-9de7-7e494da0eb10'
anns = list(GroundTruthAnnotationModel.objects.filter(document_id=doc_id).order_by('field_name'))
print(f'Document {doc_id}: {len(anns)} annotations')
for ann in anns:
    val = ann.value
    val_type = type(val).__name__
    if isinstance(val, list):
        val_preview = f'list[{len(val)}] first item type={type(val[0]).__name__ if val else "empty"}'
        if val and isinstance(val[0], dict):
            val_preview += f' keys={list(val[0].keys())[:5]}'
    else:
        val_preview = str(val)[:80]
    print(f'  {ann.field_name}: type={val_type} val={val_preview}')

