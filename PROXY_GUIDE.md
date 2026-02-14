# Proxy Configuration Guide

## How to Use Proxies

The bot is already proxy-ready. To use proxies:

### Option 1: Add to config.yaml

```yaml
proxy:
  enabled: true
  rotation: true
  list:
    - "http://username:password@proxy-host:port"
    - "http://proxy2.example.com:8080"
    - "socks5://user:pass@socks-proxy.com:1080"
```

### Option 2: Use a proxy file

Create `proxies.txt` in the project root:

```
http://proxy1.example.com:8080
http://user:pass@proxy2.example.com:3128
socks5://proxy3.example.com:1080
```

Then in config.yaml:

```yaml
proxy:
  enabled: true
  rotation: true
  file: "proxies.txt"
```

## Recommended Proxy Services

For bypassing rate limits on Indian stores, use:

1. **Residential Proxies** (Best for e-commerce):
   - Bright Data (formerly Luminati)
   - Smartproxy
   - Oxylabs
   - GeoSurf

2. **Datacenter Proxies** (Cheaper):
   - ProxyRack
   - MyPrivateProxy
   - HighProxies

3. **Indian IP Addresses**:
   - Use proxies specifically in India (Mumbai, Delhi, Bangalore)
   - Many stores detect non-Indian IPs

## Current Rate Limit Issue

The EasySell API has blocked our current IP after placing test order #D7368.

**To place new orders immediately:**
1. Get working proxies (paid services are reliable)
2. Add them to config.yaml
3. Run the bot - it will automatically rotate proxies

**Or wait:** The rate limit typically resets after a few hours or 24 hours.

## Testing Your Proxies

Before adding to config, test them:

```bash
curl -x http://your-proxy:port https://api.ipify.org
```

Should return the proxy's IP, not your real IP.
