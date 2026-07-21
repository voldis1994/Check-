#ifndef __SYSTEM_STATUS_MQH__
#define __SYSTEM_STATUS_MQH__

#property strict

#include <SYSTEM_Export.mqh>

#define SYSTEM_PROTOCOL_SCHEMA_VERSION "1.0.0"
#define SYSTEM_EA_VERSION "1.1.4"
#define SYSTEM_STATUS_FILENAME_TEMPLATE "status_%s.json"
#define SYSTEM_CLOSED_FILENAME_TEMPLATE "closed_%s_%d.json"

string SYSTEM_GetProtocolSchemaVersion()
{
   return SYSTEM_PROTOCOL_SCHEMA_VERSION;
}

string SYSTEM_GetEaVersion()
{
   return SYSTEM_EA_VERSION;
}

string SYSTEM_FormatJsonBoolean(const bool value)
{
   return value ? "true" : "false";
}

string SYSTEM_FormatJsonNumber(const double value, const int digits)
{
   return DoubleToString(value, digits);
}

string SYSTEM_EscapeJsonString(const string value)
{
   string escaped = value;
   StringReplace(escaped, "\\", "\\\\");
   StringReplace(escaped, "\"", "\\\"");
   return escaped;
}

string SYSTEM_BuildStatusFilePath(const string account_id)
{
   string filename = StringFormat(SYSTEM_STATUS_FILENAME_TEMPLATE, account_id);
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), filename);
}

string SYSTEM_BuildClosedTradeFilePath(const string account_id, const string symbol, const int magic)
{
   string filename = StringFormat(SYSTEM_CLOSED_FILENAME_TEMPLATE, symbol, magic);
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), filename);
}

bool SYSTEM_FindOpenPositionForInstance(
   const string symbol,
   const int magic,
   int &ticket,
   string &side,
   double &volume,
   double &entry_price,
   double &stop_loss,
   double &take_profit
)
{
   ticket = 0;
   side = "";
   volume = 0.0;
   entry_price = 0.0;
   stop_loss = 0.0;
   take_profit = 0.0;

   for(int index = OrdersTotal() - 1; index >= 0; index--)
   {
      if(!OrderSelect(index, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() != symbol)
         continue;
      if(OrderMagicNumber() != magic)
         continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL)
         continue;

      ticket = OrderTicket();
      side = (OrderType() == OP_BUY) ? "BUY" : "SELL";
      volume = OrderLots();
      entry_price = OrderOpenPrice();
      stop_loss = OrderStopLoss();
      take_profit = OrderTakeProfit();
      return true;
   }
   return false;
}

string SYSTEM_BuildOpenPositionEntryJson(
   const string symbol,
   const int magic,
   const int ticket,
   const string side,
   const double volume,
   const double entry_price,
   const double stop_loss,
   const double take_profit,
   const datetime open_time,
   const string order_comment,
   const double profit,
   const double swap,
   const double commission
)
{
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits <= 0)
      digits = 5;

   string json = "    {\n";
   json = json + "      \"symbol\": \"" + SYSTEM_EscapeJsonString(symbol) + "\",\n";
   json = json + "      \"magic\": " + IntegerToString(magic) + ",\n";
   json = json + "      \"ticket\": " + IntegerToString(ticket) + ",\n";
   json = json + "      \"side\": \"" + SYSTEM_EscapeJsonString(side) + "\",\n";
   json = json + "      \"volume\": " + SYSTEM_FormatJsonNumber(volume, 2) + ",\n";
   json = json + "      \"entry_price\": " + SYSTEM_FormatJsonNumber(entry_price, digits) + ",\n";
   json = json + "      \"stop_loss\": " + SYSTEM_FormatJsonNumber(stop_loss, digits) + ",\n";
   json = json + "      \"take_profit\": " + SYSTEM_FormatJsonNumber(take_profit, digits);
   if(open_time > 0)
      json = json + ",\n      \"open_time_utc\": \"" + SYSTEM_FormatTimeUtc(open_time) + "\"";
   if(StringLen(order_comment) > 0)
      json = json + ",\n      \"order_comment\": \"" + SYSTEM_EscapeJsonString(order_comment) + "\"";
   json = json + ",\n      \"profit\": " + SYSTEM_FormatJsonNumber(profit, 2);
   json = json + ",\n      \"swap\": " + SYSTEM_FormatJsonNumber(swap, 2);
   json = json + ",\n      \"commission\": " + SYSTEM_FormatJsonNumber(commission, 2);
   json = json + "\n    }";
   return json;
}

string SYSTEM_BuildOpenPositionsJson()
{
   string json = "";
   int count = 0;

   for(int index = OrdersTotal() - 1; index >= 0; index--)
   {
      if(!OrderSelect(index, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL)
         continue;

      string side = (OrderType() == OP_BUY) ? "BUY" : "SELL";
      if(count == 0)
         json = ",\n  \"open_positions\": [\n";
      else
         json = json + ",\n";

      json = json + SYSTEM_BuildOpenPositionEntryJson(
         OrderSymbol(),
         OrderMagicNumber(),
         OrderTicket(),
         side,
         OrderLots(),
         OrderOpenPrice(),
         OrderStopLoss(),
         OrderTakeProfit(),
         OrderOpenTime(),
         OrderComment(),
         OrderProfit(),
         OrderSwap(),
         OrderCommission()
      );
      count++;
   }

   if(count > 0)
      json = json + "\n  ]";
   return json;
}

string SYSTEM_BuildStatusJson(
   const string account_id,
   const bool connected,
   const bool trade_allowed,
   const double balance,
   const double equity,
   const double margin_free,
   const string last_error,
   const string symbol,
   const int magic
)
{
   string timestamp_utc = SYSTEM_FormatTimeUtc(TimeCurrent());
   string json = "{\n";
   json = json + "  \"account_id\": \"" + SYSTEM_EscapeJsonString(account_id) + "\",\n";
   json = json + "  \"balance\": " + SYSTEM_FormatJsonNumber(balance, 2) + ",\n";
   json = json + "  \"connected\": " + SYSTEM_FormatJsonBoolean(connected) + ",\n";
   json = json + "  \"ea_version\": \"" + SYSTEM_EscapeJsonString(SYSTEM_GetEaVersion()) + "\",\n";
   json = json + "  \"equity\": " + SYSTEM_FormatJsonNumber(equity, 2) + ",\n";
   json = json + "  \"margin_free\": " + SYSTEM_FormatJsonNumber(margin_free, 2) + ",\n";
   json = json + "  \"schema_version\": \"" + SYSTEM_EscapeJsonString(SYSTEM_GetProtocolSchemaVersion()) + "\",\n";
   json = json + "  \"timestamp_utc\": \"" + timestamp_utc + "\",\n";
   json = json + "  \"trade_allowed\": " + SYSTEM_FormatJsonBoolean(trade_allowed);
   if(StringLen(last_error) > 0)
      json = json + ",\n  \"last_error\": \"" + SYSTEM_EscapeJsonString(last_error) + "\"";
   json = json + SYSTEM_BuildOpenPositionsJson();
   double tick_value = MarketInfo(symbol, MODE_TICKVALUE);
   double tick_size = MarketInfo(symbol, MODE_TICKSIZE);
   int stop_level = (int)MarketInfo(symbol, MODE_STOPLEVEL);
   int freeze_level = (int)MarketInfo(symbol, MODE_FREEZELEVEL);
   if(tick_value > 0.0)
      json = json + ",\n  \"tick_value\": " + SYSTEM_FormatJsonNumber(tick_value, 5);
   if(tick_size > 0.0)
      json = json + ",\n  \"tick_size\": " + SYSTEM_FormatJsonNumber(tick_size, 5);
   json = json + ",\n  \"stop_level\": " + IntegerToString(stop_level);
   json = json + ",\n  \"freeze_level\": " + IntegerToString(freeze_level);
   json = json + "\n}\n";
   return json;
}

string SYSTEM_BuildStatusJsonFromAccount(const string account_id, const string symbol, const int magic)
{
   return SYSTEM_BuildStatusJson(
      account_id,
      IsConnected(),
      IsTradeAllowed(),
      AccountBalance(),
      AccountEquity(),
      AccountFreeMargin(),
      "",
      symbol,
      magic
   );
}

bool SYSTEM_ExportStatus(const string account_id, const string symbol, const int magic)
{
   if(StringLen(account_id) == 0)
      return false;
   if(!SYSTEM_EnsureAccountDirectories(account_id))
      return false;

   string path = SYSTEM_BuildStatusFilePath(account_id);
   string payload = SYSTEM_BuildStatusJsonFromAccount(account_id, symbol, magic);
   return SYSTEM_AtomicWriteText(path, payload);
}

bool SYSTEM_ExportStatusWithLastError(
   const string account_id,
   const string symbol,
   const int magic,
   const string last_error
)
{
   if(StringLen(account_id) == 0)
      return false;
   if(!SYSTEM_EnsureAccountDirectories(account_id))
      return false;

   string path = SYSTEM_BuildStatusFilePath(account_id);
   string payload = SYSTEM_BuildStatusJson(
      account_id,
      IsConnected(),
      IsTradeAllowed(),
      AccountBalance(),
      AccountEquity(),
      AccountFreeMargin(),
      last_error,
      symbol,
      magic
   );
   return SYSTEM_AtomicWriteText(path, payload);
}

string SYSTEM_DetermineCloseReason()
{
   double close_price = OrderClosePrice();
   double stop_loss = OrderStopLoss();
   double take_profit = OrderTakeProfit();
   double point = MarketInfo(OrderSymbol(), MODE_POINT);
   if(point <= 0.0)
      point = 0.00001;
   double tolerance = point * 3.0;

   if(stop_loss > 0.0 && MathAbs(close_price - stop_loss) <= tolerance)
      return "stop_loss";
   if(take_profit > 0.0 && MathAbs(close_price - take_profit) <= tolerance)
      return "take_profit";
   return "closed";
}

bool SYSTEM_FindLastClosedOrderForInstance(
   const string symbol,
   const int magic,
   int &ticket,
   double &close_price,
   datetime &close_time,
   double &profit,
   double &commission,
   double &swap,
   string &close_reason,
   string &side,
   double &volume,
   string &order_comment
)
{
   ticket = 0;
   close_price = 0.0;
   close_time = 0;
   profit = 0.0;
   commission = 0.0;
   swap = 0.0;
   close_reason = "";
   side = "";
   volume = 0.0;
   order_comment = "";

   datetime best_close_time = 0;
   bool found = false;

   for(int index = OrdersHistoryTotal() - 1; index >= 0; index--)
   {
      if(!OrderSelect(index, SELECT_BY_POS, MODE_HISTORY))
         continue;
      if(OrderSymbol() != symbol)
         continue;
      if(OrderMagicNumber() != magic)
         continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL)
         continue;
      if(OrderCloseTime() <= 0)
         continue;

      if(!found || OrderCloseTime() > best_close_time)
      {
         found = true;
         best_close_time = OrderCloseTime();
         ticket = OrderTicket();
         close_price = OrderClosePrice();
         close_time = OrderCloseTime();
         profit = OrderProfit();
         commission = OrderCommission();
         swap = OrderSwap();
         close_reason = SYSTEM_DetermineCloseReason();
         side = (OrderType() == OP_BUY) ? "BUY" : "SELL";
         volume = OrderLots();
         order_comment = OrderComment();
      }
   }
   return found;
}

string SYSTEM_BuildClosedTradeJson(
   const string account_id,
   const string symbol,
   const int magic,
   const int ticket,
   const double close_price,
   const datetime close_time,
   const double profit,
   const double commission,
   const double swap,
   const string close_reason,
   const string side,
   const double volume,
   const string order_comment
)
{
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits <= 0)
      digits = 5;

   string json = "{\n";
   json = json + "  \"account_id\": \"" + SYSTEM_EscapeJsonString(account_id) + "\",\n";
   json = json + "  \"symbol\": \"" + SYSTEM_EscapeJsonString(symbol) + "\",\n";
   json = json + "  \"magic\": " + IntegerToString(magic) + ",\n";
   json = json + "  \"ticket\": " + IntegerToString(ticket) + ",\n";
   json = json + "  \"close_price\": " + SYSTEM_FormatJsonNumber(close_price, digits) + ",\n";
   json = json + "  \"close_time_utc\": \"" + SYSTEM_FormatTimeUtc(close_time) + "\",\n";
   json = json + "  \"profit\": " + SYSTEM_FormatJsonNumber(profit, 2) + ",\n";
   json = json + "  \"commission\": " + SYSTEM_FormatJsonNumber(commission, 2) + ",\n";
   json = json + "  \"swap\": " + SYSTEM_FormatJsonNumber(swap, 2);
   if(StringLen(close_reason) > 0)
      json = json + ",\n  \"close_reason\": \"" + SYSTEM_EscapeJsonString(close_reason) + "\"";
   if(StringLen(side) > 0)
      json = json + ",\n  \"side\": \"" + SYSTEM_EscapeJsonString(side) + "\"";
   if(volume > 0.0)
      json = json + ",\n  \"volume\": " + SYSTEM_FormatJsonNumber(volume, 2);
   if(StringLen(order_comment) > 0)
      json = json + ",\n  \"order_comment\": \"" + SYSTEM_EscapeJsonString(order_comment) + "\"";
   json = json + "\n}\n";
   return json;
}

bool SYSTEM_ExportClosedTrade(const string account_id, const string symbol, const int magic)
{
   if(StringLen(account_id) == 0 || StringLen(symbol) == 0)
      return false;
   if(!SYSTEM_EnsureAccountDirectories(account_id))
      return false;

   int ticket = 0;
   double close_price = 0.0;
   datetime close_time = 0;
   double profit = 0.0;
   double commission = 0.0;
   double swap = 0.0;
   string close_reason = "";
   string side = "";
   double volume = 0.0;
   string order_comment = "";

   if(!SYSTEM_FindLastClosedOrderForInstance(
      symbol,
      magic,
      ticket,
      close_price,
      close_time,
      profit,
      commission,
      swap,
      close_reason,
      side,
      volume,
      order_comment
   ))
      return true;

   string path = SYSTEM_BuildClosedTradeFilePath(account_id, symbol, magic);
   string payload = SYSTEM_BuildClosedTradeJson(
      account_id,
      symbol,
      magic,
      ticket,
      close_price,
      close_time,
      profit,
      commission,
      swap,
      close_reason,
      side,
      volume,
      order_comment
   );
   return SYSTEM_AtomicWriteText(path, payload);
}

bool SYSTEM_StatusPerformsAnalysis()
{
   return false;
}

#endif
