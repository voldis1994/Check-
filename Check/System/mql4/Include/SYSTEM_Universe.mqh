#ifndef __SYSTEM_UNIVERSE_MQH__
#define __SYSTEM_UNIVERSE_MQH__

#property strict

#include "SYSTEM_Status.mqh"

#define SYSTEM_UNIVERSE_FILENAME "universe.json"
#define SYSTEM_SESSION_ASIA "ASIA"
#define SYSTEM_SESSION_LONDON "LONDON"
#define SYSTEM_SESSION_NEW_YORK "NEW_YORK"
#define SYSTEM_SESSION_OFF "OFF"
#define SYSTEM_REGIME_TRENDING "trending"
#define SYSTEM_REGIME_RANGING "ranging"
#define SYSTEM_REGIME_VOLATILE "volatile"
#define SYSTEM_REGIME_QUIET "quiet"
#define SYSTEM_NEWS_IMPACT_LOW "low"
#define SYSTEM_REGIME_ATR_PERIOD 14
#define SYSTEM_REGIME_MEDIAN_BARS 50
#define SYSTEM_REGIME_TREND_LOOKBACK 20
#define SYSTEM_REGIME_VOLATILE_MULT 1.6
#define SYSTEM_REGIME_QUIET_MULT 0.55
#define SYSTEM_REGIME_TREND_MULT 2.0

bool SYSTEM_IsUniverseForbiddenField(const string field_name)
{
   return field_name == "signal"
      || field_name == "direction"
      || field_name == "trade"
      || field_name == "buy"
      || field_name == "sell"
      || field_name == "action";
}

string SYSTEM_BuildUniverseFilePath(const string account_id)
{
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), SYSTEM_UNIVERSE_FILENAME);
}

string SYSTEM_DetectTradingSession()
{
   MqlDateTime parts;
   TimeToStruct(TimeGMT(), parts);
   int hour = parts.hour;

   if(hour >= 0 && hour < 8)
      return SYSTEM_SESSION_ASIA;
   if(hour >= 8 && hour < 13)
      return SYSTEM_SESSION_LONDON;
   if(hour >= 13 && hour < 22)
      return SYSTEM_SESSION_NEW_YORK;
   return SYSTEM_SESSION_OFF;
}

double SYSTEM_MedianOfDoubles(double &values[], const int count)
{
   if(count <= 0)
      return 0.0;

   for(int i = 0; i < count - 1; i++)
   {
      for(int j = i + 1; j < count; j++)
      {
         if(values[i] > values[j])
         {
            double tmp = values[i];
            values[i] = values[j];
            values[j] = tmp;
         }
      }
   }

   if((count % 2) == 1)
      return values[count / 2];
   return (values[(count / 2) - 1] + values[count / 2]) / 2.0;
}

string SYSTEM_DetectMarketRegime()
{
   string symbol = Symbol();
   int bars_needed = SYSTEM_REGIME_MEDIAN_BARS + 1;
   if(SYSTEM_REGIME_TREND_LOOKBACK + 1 > bars_needed)
      bars_needed = SYSTEM_REGIME_TREND_LOOKBACK + 1;
   if(iBars(symbol, PERIOD_M1) < bars_needed)
      return SYSTEM_REGIME_RANGING;

   double atr_sum = 0.0;
   for(int atr_shift = 1; atr_shift <= SYSTEM_REGIME_ATR_PERIOD; atr_shift++)
      atr_sum += iHigh(symbol, PERIOD_M1, atr_shift) - iLow(symbol, PERIOD_M1, atr_shift);
   double atr = atr_sum / (double)SYSTEM_REGIME_ATR_PERIOD;

   double ranges[];
   ArrayResize(ranges, SYSTEM_REGIME_MEDIAN_BARS);
   for(int range_shift = 1; range_shift <= SYSTEM_REGIME_MEDIAN_BARS; range_shift++)
      ranges[range_shift - 1] = iHigh(symbol, PERIOD_M1, range_shift) - iLow(symbol, PERIOD_M1, range_shift);

   double median_range = SYSTEM_MedianOfDoubles(ranges, SYSTEM_REGIME_MEDIAN_BARS);
   if(median_range <= 0.0)
      return SYSTEM_REGIME_RANGING;

   if(atr > SYSTEM_REGIME_VOLATILE_MULT * median_range)
      return SYSTEM_REGIME_VOLATILE;
   if(atr < SYSTEM_REGIME_QUIET_MULT * median_range)
      return SYSTEM_REGIME_QUIET;

   double directional = MathAbs(
      iClose(symbol, PERIOD_M1, 1) - iClose(symbol, PERIOD_M1, SYSTEM_REGIME_TREND_LOOKBACK)
   );
   if(directional > SYSTEM_REGIME_TREND_MULT * atr)
      return SYSTEM_REGIME_TRENDING;
   return SYSTEM_REGIME_RANGING;
}

string SYSTEM_BuildUniverseJson(
   const string session,
   const string market_regime,
   const bool news_window_active,
   const string news_impact_level,
   const string metadata_json
)
{
   string timestamp_utc = SYSTEM_FormatTimeUtc(TimeCurrent());
   string json = "{\n";
   json = json + "  \"market_regime\": \"" + SYSTEM_EscapeJsonString(market_regime) + "\",\n";
   json = json + "  \"news_window_active\": " + SYSTEM_FormatJsonBoolean(news_window_active) + ",\n";
   json = json + "  \"schema_version\": \"" + SYSTEM_EscapeJsonString(SYSTEM_GetProtocolSchemaVersion()) + "\",\n";
   json = json + "  \"session\": \"" + SYSTEM_EscapeJsonString(session) + "\",\n";
   json = json + "  \"timestamp_utc\": \"" + timestamp_utc + "\"";
   if(StringLen(news_impact_level) > 0)
      json = json + ",\n  \"news_impact_level\": \"" + SYSTEM_EscapeJsonString(news_impact_level) + "\"";
   if(StringLen(metadata_json) > 0)
      json = json + ",\n  \"metadata\": " + metadata_json;
   json = json + "\n}\n";
   return json;
}

string SYSTEM_BuildUniverseJsonFromContext()
{
   string metadata = "{\"news_data_available\": false, \"news_filter\": \"disabled_no_calendar\"}";
   return SYSTEM_BuildUniverseJson(
      SYSTEM_DetectTradingSession(),
      SYSTEM_DetectMarketRegime(),
      false,
      SYSTEM_NEWS_IMPACT_LOW,
      metadata
   );
}

bool SYSTEM_ExportUniverse(const string account_id)
{
   if(StringLen(account_id) == 0)
      return false;
   if(!SYSTEM_EnsureAccountDirectories(account_id))
      return false;

   string path = SYSTEM_BuildUniverseFilePath(account_id);
   string payload = SYSTEM_BuildUniverseJsonFromContext();
   return SYSTEM_AtomicWriteText(path, payload);
}

bool SYSTEM_UniversePerformsAnalysis()
{
   return false;
}

#endif
