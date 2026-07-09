#ifndef __SYSTEM_UNIVERSE_MQH__
#define __SYSTEM_UNIVERSE_MQH__

#property strict

#include <SYSTEM_Status.mqh>

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

string SYSTEM_DetectMarketRegime()
{
   return SYSTEM_REGIME_RANGING;
}

string SYSTEM_BuildUniverseJson(
   const string session,
   const string market_regime,
   const bool news_window_active,
   const string news_impact_level
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
   json = json + "\n}\n";
   return json;
}

string SYSTEM_BuildUniverseJsonFromContext()
{
   return SYSTEM_BuildUniverseJson(
      SYSTEM_DetectTradingSession(),
      SYSTEM_DetectMarketRegime(),
      false,
      SYSTEM_NEWS_IMPACT_LOW
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
