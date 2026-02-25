"""Generate Pydantic schemas from field definitions for structured extraction."""

from typing import Any

from pydantic import BaseModel, Field, create_model

from uu_backend.models.taxonomy import FieldType, SchemaField


def generate_pydantic_schema(
    schema_fields: list[SchemaField], model_name: str = "ExtractionSchema"
) -> type[BaseModel]:
    """
    Generate a Pydantic model from schema field definitions.

    This allows us to use OpenAI's structured output with response_format.

    Args:
        schema_fields: List of schema field definitions
        model_name: Name for the generated Pydantic model

    Returns:
        Dynamically created Pydantic model class
    """
    field_definitions = {}

    for field in schema_fields:
        python_type = _field_type_to_python_type(field)
        field_info = Field(
            description=field.description, default=None if not field.required else ...
        )
        field_definitions[field.name] = (python_type, field_info)

    # Create the Pydantic model dynamically
    return create_model(model_name, **field_definitions)


def _field_type_to_python_type(field: SchemaField) -> Any:
    """Convert SchemaField to Python type annotation."""

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
            item_type = _field_type_to_python_type(field.items)
            return list[item_type]
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
                prop_field = Field(description=prop_schema.description, default=None)
                nested_fields[prop_name] = (prop_type, prop_field)

            # Create nested model
            nested_model = create_model(
                f"{field.name.title().replace('_', '')}Object", **nested_fields
            )
            return nested_model
        return dict[str, Any]

    return Any


def schema_to_json_schema(pydantic_model: type[BaseModel]) -> dict:
    """
    Convert Pydantic model to JSON schema for OpenAI.

    Args:
        pydantic_model: Pydantic model class

    Returns:
        JSON schema dict
    """
    return pydantic_model.model_json_schema()


def validate_extraction(data: dict, pydantic_model: type[BaseModel]) -> BaseModel:
    """
    Validate extracted data against Pydantic schema.

    Args:
        data: Extracted data dictionary
        pydantic_model: Pydantic model to validate against

    Returns:
        Validated Pydantic model instance

    Raises:
        ValidationError if data doesn't match schema
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
