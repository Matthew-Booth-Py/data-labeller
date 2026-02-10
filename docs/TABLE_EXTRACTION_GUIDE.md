# Table Extraction Guide

## Creating Array Fields for Table Data

The UI now supports creating nested array fields for extracting tabular data (like claim items, invoice line items, etc.).

## Step-by-Step: Creating a Claim Items Field

### 1. Navigate to Schema Tab
- Open your project
- Go to **Schema** → **Document Types** tab
- Select or create a document type (e.g., "Auto Repair Claim")

### 2. Add Array Field
1. Click **"Add Field"**
2. Fill in the basics:
   - **Field Name**: `claim_items`
   - **Type**: Select **"Array"**
   - **Description**: "List of claimed items with descriptions and costs"

### 3. Configure Array Items
Once you select "Array", you'll see **Array Item Configuration**:

1. **Item Type**: Select **"Object (for tables)"**
   - This tells the system each array item is a structured object with multiple properties

### 4. Add Object Properties
Click **"Add Property"** for each column in your table:

#### Property 1: Item Name
- **Property name**: `item_name`
- **Type**: `String`
- **Description**: "Name of the damaged item"

#### Property 2: Description
- **Property name**: `description`
- **Type**: `String`
- **Description**: "Description of damage/work"

#### Property 3: Cost
- **Property name**: `estimated_cost`
- **Type**: `Number`
- **Description**: "Cost in dollars"

### 5. Preview & Save
You'll see a preview of the expected output:
```json
{
  "claim_items": [
    {
      "item_name": "value",
      "description": "value",
      "estimated_cost": 0
    }
  ]
}
```

Click **"Add Field"** to save.

### 6. Add Other Fields
Don't forget to add the total:
- **Field Name**: `total_estimate`
- **Type**: `Number`
- **Description**: "Total estimated cost from the table"

## Complete Example Schema

Your final schema will look like this:

```json
{
  "name": "Auto Repair Claim",
  "schema_fields": [
    {
      "name": "claim_items",
      "type": "array",
      "description": "List of claimed items with descriptions and costs",
      "items": {
        "type": "object",
        "properties": {
          "item_name": {
            "type": "string",
            "description": "Name of the damaged item"
          },
          "description": {
            "type": "string",
            "description": "Description of damage/work"
          },
          "estimated_cost": {
            "type": "number",
            "description": "Cost in dollars"
          }
        }
      }
    },
    {
      "name": "total_estimate",
      "type": "number",
      "description": "Total estimated cost"
    }
  ]
}
```

## Labeling Documents

### Create Labels for Each Property

In the **Labels** tab, create labels matching your property names:

1. **Label**: `item_name`
   - Color: Blue
   - Description: "Item name from claim table"

2. **Label**: `description`
   - Color: Green
   - Description: "Description of damage/work"

3. **Label**: `estimated_cost`
   - Color: Orange
   - Description: "Cost amount from table"

### Annotate Your Document

For a table like this:

| Item | Description | Cost |
|------|-------------|------|
| Front Bumper | Replace - cracked | $1,450.00 |
| Hood | Repair - minor denting | $650.00 |

**Label each value:**
1. Highlight "Front Bumper" → Apply label `item_name`
2. Highlight "Replace - cracked" → Apply label `description`
3. Highlight "$1,450.00" → Apply label `estimated_cost`
4. Highlight "Hood" → Apply label `item_name`
5. Highlight "Repair - minor denting" → Apply label `description`
6. Highlight "$650.00" → Apply label `estimated_cost`

## How Evaluation Works

The evaluation system will:

1. **Group annotations by label**:
   - `item_name`: ["Front Bumper", "Hood"]
   - `description`: ["Replace - cracked", "Repair - minor denting"]
   - `estimated_cost`: ["$1,450.00", "$650.00"]

2. **Build ground truth array**:
```json
{
  "claim_items": [
    {
      "item_name": "Front Bumper",
      "description": "Replace - cracked",
      "estimated_cost": 1450.00
    },
    {
      "item_name": "Hood",
      "description": "Repair - minor denting",
      "estimated_cost": 650.00
    }
  ]
}
```

3. **Compare against extraction**:
   - Check if same number of items
   - Compare each property in each item
   - Calculate F1, precision, recall

## Expected Extraction Output

When you run extraction, you'll get:

```json
{
  "claim_items": [
    {
      "item_name": "Front Bumper",
      "description": "Replace - cracked and dented",
      "estimated_cost": 1450.00
    },
    {
      "item_name": "Hood",
      "description": "Repair - minor denting",
      "estimated_cost": 650.00
    },
    {
      "item_name": "Headlight Assembly (L)",
      "description": "Replace - broken",
      "estimated_cost": 890.00
    },
    {
      "item_name": "Labor",
      "description": "Estimated 8 hours",
      "estimated_cost": 960.00
    }
  ],
  "total_estimate": 3950.00
}
```

## Tips

### For Better Extraction
1. **Use clear property names** that match table headers
2. **Add descriptions** to guide the LLM
3. **Label consistently** - same pattern for all rows

### For Better Evaluation
1. **Label all rows** in your validation documents
2. **Label in order** (top to bottom) for easier debugging
3. **Use normalized values** - remove $ and commas in annotations if possible

### Common Patterns

#### Invoice Line Items
```
Properties: item_description, quantity, unit_price, total
```

#### Expense Report
```
Properties: date, category, merchant, amount
```

#### Property Damage List
```
Properties: item, condition, replacement_cost
```

## UI Features

### Visual Indicators
- **Array fields** show a `type[]` badge (e.g., `object[]`)
- **Nested properties** are displayed in a collapsible section
- **Example preview** shows expected JSON structure

### Editing
- Click **Edit** (pencil icon) to modify extraction prompts
- Click **Delete** (trash icon) to remove fields
- Drag fields to reorder (coming soon)

## Troubleshooting

### "Add Field" button is disabled
- Make sure you've added at least one property for object arrays
- Check that property names are filled in

### Extraction returns empty array
- Verify labels match property names
- Check that documents are annotated
- Review extraction prompt for the field

### Evaluation shows low F1 score
- Check if annotation order matches extraction order
- Verify all rows are labeled
- Look at field-level metrics to see which properties are wrong

## Next Steps

1. Create your schema with array fields
2. Label 20-30 documents
3. Run extraction
4. Run evaluation to measure quality
5. Iterate on prompts to improve

See [EVALUATION_QUICKSTART.md](./EVALUATION_QUICKSTART.md) for more on the evaluation workflow.
