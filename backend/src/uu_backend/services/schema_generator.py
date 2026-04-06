"""Generate Pydantic schemas from field definitions for structured extraction."""

from typing import Any

from pydantic import BaseModel, Field, create_model

from uu_backend.models.taxonomy import FieldType, SchemaField


def generate_pydantic_schema(
    schema_fields: list[SchemaField], model_name: str = "ExtractionSchema"
) -> type[BaseModel]:
    """Generate a Pydantic model from schema field definitions.

    Parameters
    ----------
    schema_fields : list of SchemaField
        Field definitions to include in the model.
    model_name : str, optional
        Name for the generated Pydantic model class.

    Returns
    -------
    type[BaseModel]
        Dynamically created Pydantic model class.
    """
    field_definitions = {}

    for field in schema_fields:
        python_type = _field_type_to_python_type(field)
        field_annotation = python_type if field.required else _optional_annotation(python_type)
        field_info = Field(
            description=field.description, default=None if not field.required else ...
        )
        field_definitions[field.name] = (field_annotation, field_info)

    # Create the Pydantic model dynamically
    return create_model(model_name, **field_definitions)


def _field_type_to_python_type(field: SchemaField, model_name_prefix: str | None = None) -> Any:
    if field.type == FieldType.STRING:
        return str

    elif field.type == FieldType.NUMBER:
        return float

    elif field.type == FieldType.DATE:
        return str  # Keep as string for flexibility

    elif field.type == FieldType.BOOLEAN:
        return bool

    elif field.type == FieldType.ARRAY:
        if field.items:
            # Use the parent array field's name as the prefix so that two array-of-object fields
            # whose item schemas both carry the generic name "item" produce distinct Pydantic model
            # names (e.g. "QuarterlyFinancialHighlightsItem" vs "BusinessUnitRevenueTableItem")
            # and therefore distinct $defs entries in the JSON Schema sent to OpenAI.
            item_type_result = _field_type_to_python_type(field.items, model_name_prefix=field.name)
            return list[item_type_result]  # type: ignore
        return list[Any]

    elif field.type == FieldType.OBJECT:
        if field.properties:
            # Create nested Pydantic model for object
            nested_fields = {}
            # Sort properties by order field to preserve user-defined order
            sorted_props = sorted(
                field.properties.items(),
                key=lambda x: x[1].order if x[1].order is not None else float("inf"),
            )
            for prop_name, prop_schema in sorted_props:
                prop_type = _field_type_to_python_type(prop_schema)
                prop_annotation = (
                    prop_type if prop_schema.required else _optional_annotation(prop_type)
                )
                prop_field = Field(
                    description=prop_schema.description,
                    default=None if not prop_schema.required else ...,
                )
                nested_fields[prop_name] = (prop_annotation, prop_field)

            # Use the caller-supplied prefix when available (e.g. parent array field name),
            # falling back to the field's own name so standalone object fields still work.
            prefix = model_name_prefix if model_name_prefix is not None else field.name
            nested_model = create_model(f"{prefix.title().replace('_', '')}Item", **nested_fields)
            return nested_model
        return dict[str, Any]

    return Any


def _optional_annotation(python_type: Any) -> Any:
    if python_type is Any:
        return Any
    return python_type | None


def schema_to_json_schema(pydantic_model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to a JSON schema dict.

    Parameters
    ----------
    pydantic_model : type[BaseModel]
        Pydantic model class to convert.

    Returns
    -------
    dict
        JSON schema representation of the model.
    """
    return pydantic_model.model_json_schema()


def validate_extraction(data: dict, pydantic_model: type[BaseModel]) -> BaseModel:
    """Validate extracted data against a Pydantic schema.

    Parameters
    ----------
    data : dict
        Extracted data dictionary.
    pydantic_model : type[BaseModel]
        Pydantic model to validate against.

    Returns
    -------
    BaseModel
        Validated Pydantic model instance.

    Raises
    ------
    ValidationError
        If data does not match the schema.
    """
    return pydantic_model.model_validate(data)


# Example usage:
#
# schema_fields = [
#     SchemaField(name="invoice_number", type=FieldType.STRING, required=True),
#     SchemaField(
#         name="line_items",
#         type=FieldType.ARRAY,
#         items=SchemaField(
#             name="item",
#             type=FieldType.OBJECT,
#             properties={
#                 "description": SchemaField(name="description", type=FieldType.STRING),
#                 "amount": SchemaField(name="amount", type=FieldType.NUMBER)
#             }
#         )
#     )
# ]
#
# ExtractionModel = generate_pydantic_schema(schema_fields, "InvoiceExtraction")
# json_schema = schema_to_json_schema(ExtractionModel)
#
# # Use with OpenAI:
# response = client.chat.completions.create(
#     model="gpt-4o",
#     messages=[...],
#     response_format={
#         "type": "json_schema",
#         "json_schema": {
#             "name": "InvoiceExtraction",
#             "schema": json_schema,
#             "strict": True
#         }
#     }
# )
