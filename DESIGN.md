{
  "key": "new_checkout",
  "enabled": true,
  "default_value": false,
  "rules": [
    {
      "priority": 1,
      "conditions": [
        {
          "attribute": "country",
          "operator": "equals",
          "value": "IN"
        }
      ],
      "serve": {
        "type": "percentage",
        "true_percentage": 15
      }
    }
  ]
}