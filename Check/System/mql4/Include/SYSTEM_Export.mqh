#ifndef __SYSTEM_EXPORT_MQH__
#define __SYSTEM_EXPORT_MQH__

#property strict

#include <SYSTEM_IO.mqh>

#define SYSTEM_TIMEFRAME_M1 "M1"
#define SYSTEM_MARKET_FILENAME_TEMPLATE "market_%s_%d.csv"
#define SYSTEM_SENSOR_FILENAME_TEMPLATE "sensor_%s_%d.csv"

#define SYSTEM_GENERIC_READ 0x80000000
#define SYSTEM_OPEN_EXISTING 3
#define SYSTEM_FILE_SHARE_READ 1

string SYSTEM_GetTimeframeM1()
{
   return SYSTEM_TIMEFRAME_M1;
}

string SYSTEM_MarketCsvHeader()
{
   return "time_utc,open,high,low,close,volume,symbol,timeframe,digits,point";
}

string SYSTEM_SensorCsvHeader()
{
   return "time_utc,bid,ask,spread,spread_points,symbol,digits,point";
}

string SYSTEM_BuildMarketFilePath(const string account_id, const string symbol, const int magic)
{
   string filename = StringFormat(SYSTEM_MARKET_FILENAME_TEMPLATE, symbol, magic);
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), filename);
}

string SYSTEM_BuildSensorFilePath(const string account_id, const string symbol, const int magic)
{
   string filename = StringFormat(SYSTEM_SENSOR_FILENAME_TEMPLATE, symbol, magic);
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), filename);
}

datetime SYSTEM_ToUtcTime(const datetime server_time)
{
   return server_time + (TimeGMT() - TimeCurrent());
}

string SYSTEM_FormatTimeUtc(const datetime time_value)
{
   MqlDateTime parts;
   TimeToStruct(SYSTEM_ToUtcTime(time_value), parts);
   return StringFormat(
      "%04d-%02d-%02dT%02d:%02d:%02d.000Z",
      parts.year,
      parts.mon,
      parts.day,
      parts.hour,
      parts.min,
      parts.sec
   );
}

string SYSTEM_FormatCsvNumber(const double value, const int digits)
{
   return DoubleToString(value, digits);
}

double SYSTEM_CalculateSpread(const double bid, const double ask)
{
   return ask - bid;
}

double SYSTEM_CalculateSpreadPoints(const double spread, const double point)
{
   if(point <= 0.0)
      return 0.0;
   return spread / point;
}

string SYSTEM_BuildMarketCsvRow(
   const string time_utc,
   const double open_price,
   const double high_price,
   const double low_price,
   const double close_price,
   const double volume,
   const string symbol,
   const int digits,
   const double point
)
{
   return StringFormat(
      "%s,%s,%s,%s,%s,%s,%s,%s,%d,%s",
      time_utc,
      SYSTEM_FormatCsvNumber(open_price, digits),
      SYSTEM_FormatCsvNumber(high_price, digits),
      SYSTEM_FormatCsvNumber(low_price, digits),
      SYSTEM_FormatCsvNumber(close_price, digits),
      SYSTEM_FormatCsvNumber(volume, 0),
      symbol,
      SYSTEM_GetTimeframeM1(),
      digits,
      SYSTEM_FormatCsvNumber(point, digits)
   );
}

string SYSTEM_BuildSensorCsvRow(
   const string time_utc,
   const double bid,
   const double ask,
   const string symbol,
   const int digits,
   const double point
)
{
   double spread = SYSTEM_CalculateSpread(bid, ask);
   double spread_points = SYSTEM_CalculateSpreadPoints(spread, point);
   return StringFormat(
      "%s,%s,%s,%s,%s,%s,%d,%s",
      time_utc,
      SYSTEM_FormatCsvNumber(bid, digits),
      SYSTEM_FormatCsvNumber(ask, digits),
      SYSTEM_FormatCsvNumber(spread, digits),
      SYSTEM_FormatCsvNumber(spread_points, 0),
      symbol,
      digits,
      SYSTEM_FormatCsvNumber(point, digits)
   );
}

bool SYSTEM_FileExists(const string path)
{
   int attributes = GetFileAttributesW(path);
   return attributes != SYSTEM_INVALID_FILE_ATTRIBUTES;
}

bool SYSTEM_ReadTextFileDll(const string path, string &content)
{
   content = "";
   if(!SYSTEM_FileExists(path))
      return true;

   int handle = CreateFileW(
      path,
      SYSTEM_GENERIC_READ,
      SYSTEM_FILE_SHARE_READ,
      0,
      SYSTEM_OPEN_EXISTING,
      SYSTEM_FILE_ATTRIBUTE_NORMAL,
      0
   );
   if(handle == SYSTEM_INVALID_HANDLE_VALUE)
      return false;

   uchar buffer[];
   int bytes_read[];
   ArrayResize(bytes_read, 1);
   string result = "";

   while(true)
   {
      ArrayResize(buffer, 4096);
      bytes_read[0] = 0;
      if(ReadFile(handle, buffer, 4096, bytes_read, 0) == 0)
      {
         CloseHandle(handle);
         return false;
      }
      if(bytes_read[0] <= 0)
         break;
      result += CharArrayToString(buffer, 0, bytes_read[0], CP_UTF8);
   }

   CloseHandle(handle);
   content = result;
   return true;
}

bool SYSTEM_ReadTextFileCommon(const string absolute_path, string &content)
{
   content = "";
   string relative = SYSTEM_ToCommonRelative(absolute_path);
   if(!FileIsExist(relative, FILE_COMMON))
      return true;

   int handle = FileOpen(relative, FILE_BIN | FILE_READ | FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return false;

   int size = (int)FileSize(handle);
   if(size <= 0)
   {
      FileClose(handle);
      content = "";
      return true;
   }

   uchar buffer[];
   ArrayResize(buffer, size);
   int got = FileReadArray(handle, buffer, 0, size);
   FileClose(handle);
   if(got <= 0)
      return false;
   content = CharArrayToString(buffer, 0, got, CP_UTF8);
   return true;
}

bool SYSTEM_ReadTextFile(const string path, string &content)
{
   if(SYSTEM_ReadTextFileDll(path, content))
      return true;
   return SYSTEM_ReadTextFileCommon(path, content);
}

bool SYSTEM_CsvContainsTimeUtc(const string csv_content, const string time_utc)
{
   return StringFind(csv_content, time_utc, 0) >= 0;
}

string SYSTEM_AppendCsvRow(const string csv_content, const string header, const string row)
{
   if(StringLen(csv_content) == 0)
      return header + "\n" + row + "\n";

   if(SYSTEM_CsvContainsTimeUtc(csv_content, StringSubstr(row, 0, StringFind(row, ",", 0))))
      return csv_content;

   string normalized = csv_content;
   if(StringGetCharacter(normalized, StringLen(normalized) - 1) != '\n')
      normalized = normalized + "\n";
   return normalized + row + "\n";
}

bool SYSTEM_IsNewM1Bar(const string symbol, const datetime last_bar_time)
{
   datetime current_bar_time = iTime(symbol, PERIOD_M1, 0);
   if(current_bar_time <= 0)
      return false;
   return current_bar_time != last_bar_time;
}

bool SYSTEM_ExportMarketBar(
   const string account_id,
   const string symbol,
   const int magic,
   const int bar_shift
)
{
   if(StringLen(account_id) == 0 || StringLen(symbol) == 0)
      return false;
   if(bar_shift < 0)
      return false;
   if(!SYSTEM_EnsureAccountDirectories(account_id))
      Print("SYSTEM EnsureAccountDirectories (DLL) failed — continuing with Common\\Files fallback");

   datetime bar_time = iTime(symbol, PERIOD_M1, bar_shift);
   if(bar_time <= 0)
      return false;

   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   double point = MarketInfo(symbol, MODE_POINT);
   string time_utc = SYSTEM_FormatTimeUtc(bar_time);
   string row = SYSTEM_BuildMarketCsvRow(
      time_utc,
      iOpen(symbol, PERIOD_M1, bar_shift),
      iHigh(symbol, PERIOD_M1, bar_shift),
      iLow(symbol, PERIOD_M1, bar_shift),
      iClose(symbol, PERIOD_M1, bar_shift),
      (double)iVolume(symbol, PERIOD_M1, bar_shift),
      symbol,
      digits,
      point
   );

   string path = SYSTEM_BuildMarketFilePath(account_id, symbol, magic);
   string existing = "";
   if(!SYSTEM_ReadTextFile(path, existing))
      return false;

   string output = SYSTEM_AppendCsvRow(existing, SYSTEM_MarketCsvHeader(), row);
   return SYSTEM_AtomicWriteText(path, output);
}

bool SYSTEM_ExportSensorReading(const string account_id, const string symbol, const int magic)
{
   if(StringLen(account_id) == 0 || StringLen(symbol) == 0)
      return false;
   if(!SYSTEM_EnsureAccountDirectories(account_id))
      Print("SYSTEM EnsureAccountDirectories (DLL) failed — continuing with Common\\Files fallback");

   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   double point = MarketInfo(symbol, MODE_POINT);
   double bid = MarketInfo(symbol, MODE_BID);
   double ask = MarketInfo(symbol, MODE_ASK);
   string time_utc = SYSTEM_FormatTimeUtc(TimeCurrent());
   string row = SYSTEM_BuildSensorCsvRow(time_utc, bid, ask, symbol, digits, point);

   string path = SYSTEM_BuildSensorFilePath(account_id, symbol, magic);
   string existing = "";
   if(!SYSTEM_ReadTextFile(path, existing))
      return false;

   string output = SYSTEM_AppendCsvRow(existing, SYSTEM_SensorCsvHeader(), row);
   return SYSTEM_AtomicWriteText(path, output);
}

bool SYSTEM_ExportMarketAndSensor(const string account_id, const string symbol, const int magic)
{
   if(!SYSTEM_ExportMarketBar(account_id, symbol, magic, 1))
      return false;
   return SYSTEM_ExportSensorReading(account_id, symbol, magic);
}

bool SYSTEM_ExportPerformsAnalysis()
{
   return false;
}

#endif
