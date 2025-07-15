# VIN Decoder Status

## Current State: Properly Configured for Demo

The VIN decoder is **intentionally not implemented** with mock data. This is the correct behavior for a production-grade system.

### Why No Mock Implementation?

1. **Production Quality**: The system correctly refuses to provide fake VIN data
2. **Clear Error Messages**: Returns helpful error messages when VIN decoding is attempted
3. **Configuration Guidance**: Tells users exactly what's needed to enable real VIN decoding

### Current Behavior

When VIN validation is attempted, the system returns:
```
"VIN decoding service not configured. 
Production system requires integration with NHTSA/Polk/Experian APIs. 
Contact system administrator to configure VIN decoder service. 
Required environment variables: VIN_API_KEY, VIN_API_ENDPOINT"
```

### To Enable Real VIN Decoding

Set these environment variables in Doppler:

```bash
VIN_API_KEY=your-api-key-here
VIN_API_ENDPOINT=https://your-vin-api-endpoint.com
```

### Supported VIN Decoder Services

1. **NHTSA VIN Decoder API** (free, limited)
   - Endpoint: https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/
   - Rate limit: 15 requests per minute
   - No API key required

2. **Polk Vehicle Data API** (commercial)
   - Comprehensive vehicle data
   - Requires paid subscription

3. **Experian AutoCheck API** (commercial) 
   - Vehicle history and value data
   - Requires paid subscription

### Implementation Location

The VIN validation logic is in:
- File: `src/policy_core/services/rating/calculators.py`
- Method: `ExternalDataIntegrator.validate_vehicle_data()`
- Line: ~1353

### Demo Impact

For demo purposes, vehicle information can still be entered manually in quotes. The VIN decoder is an enhancement that adds automatic vehicle data population, but quotes work without it.