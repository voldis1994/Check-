#ifndef __CHECK_EXPORT_MQH__
#define __CHECK_EXPORT_MQH__
#property strict

#include <CHECK_Protocol.mqh>
#include <CHECK_Json.mqh>

void CHECK_InitBridge(const string root, const string symbol, const int magic)
{
   g_check_bridge_root = CHECK_NormalizeSeparators(root);
   g_check_symbol = symbol;
   g_check_magic = magic;
   CHECK_EnsureBridgeDirectories();
   CHECK_LoadSequence();
   CHECK_LoadProcessedIds();
   g_check_last_export_ms = GetTickCount();
}

string CHECK_MarketFilePath()
{
   return CHECK_JoinPath(
      CHECK_MarketDir(),
      "market_" + g_check_symbol + "_" + IntegerToString(g_check_magic) + ".json"
   );
}

string CHECK_StatusFilePath()
{
   return CHECK_JoinPath(
      CHECK_StatusDir(),
      "status_" + IntegerToString(AccountNumber()) + ".json"
   );
}

string CHECK_BuildBarJson(const string symbol, const int shift, const bool complete)
{
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits <= 0)
      digits = 5;

   datetime open_time = iTime(symbol, PERIOD_M1, shift);
   datetime close_time = open_time + 60;
   double open_price = iOpen(symbol, PERIOD_M1, shift);
   double high_price = iHigh(symbol, PERIOD_M1, shift);
   double low_price = iLow(symbol, PERIOD_M1, shift);
   double close_price = iClose(symbol, PERIOD_M1, shift);
   long tick_volume = iVolume(symbol, PERIOD_M1, shift);

   string json = "    {\n";
   json += "      \"open_time_utc\": \"" + CHECK_FormatTimeUtc(open_time) + "\",\n";
   json += "      \"close_time_utc\": \"" + CHECK_FormatTimeUtc(close_time) + "\",\n";
   json += "      \"open\": " + CHECK_FormatJsonNumber(open_price, digits) + ",\n";
   json += "      \"high\": " + CHECK_FormatJsonNumber(high_price, digits) + ",\n";
   json += "      \"low\": " + CHECK_FormatJsonNumber(low_price, digits) + ",\n";
   json += "      \"close\": " + CHECK_FormatJsonNumber(close_price, digits) + ",\n";
   json += "      \"tick_volume\": " + IntegerToString((int)tick_volume) + ",\n";
   json += "      \"complete\": " + CHECK_FormatJsonBoolean(complete) + "\n";
   json += "    }";
   return json;
}

string CHECK_BuildBarsM1Json(const string symbol)
{
   int available = iBars(symbol, PERIOD_M1);
   int closed_count = available - 1;
   if(closed_count < 0)
      closed_count = 0;
   if(closed_count > CHECK_MARKET_BARS_MAX)
      closed_count = CHECK_MARKET_BARS_MAX;

   string json = "[\n";
   // Oldest first for aggregation consumers.
   for(int i = closed_count; i >= 1; i--)
   {
      if(i < closed_count)
         json += ",\n";
      json += CHECK_BuildBarJson(symbol, i, true);
   }
   json += "\n  ]";
   return json;
}

string CHECK_BuildMarketSnapshotJson()
{
   string symbol = g_check_symbol;
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits <= 0)
      digits = 5;
   double point = MarketInfo(symbol, MODE_POINT);
   if(point <= 0.0)
      point = MathPow(10.0, -digits);
   double pip_size = CHECK_PipSize(symbol);
   double bid = MarketInfo(symbol, MODE_BID);
   double ask = MarketInfo(symbol, MODE_ASK);
   double spread = ask - bid;
   double spread_points = (point > 0.0) ? (spread / point) : 0.0;
   double spread_pips = (pip_size > 0.0) ? (spread / pip_size) : 0.0;
   double tick_size = MarketInfo(symbol, MODE_TICKSIZE);
   double tick_value = MarketInfo(symbol, MODE_TICKVALUE);
   double min_lot = MarketInfo(symbol, MODE_MINLOT);
   double max_lot = MarketInfo(symbol, MODE_MAXLOT);
   double lot_step = MarketInfo(symbol, MODE_LOTSTEP);
   int stop_level = (int)MarketInfo(symbol, MODE_STOPLEVEL);
   int freeze_level = (int)MarketInfo(symbol, MODE_FREEZELEVEL);
   long sequence = CHECK_NextSequence();
   string generated = CHECK_NowUtcIso();
   string message_id = CHECK_NewMessageId();

   string json = "{\n";
   json += CHECK_JsonKvString("protocol_version", CHECK_PROTOCOL_VERSION, true);
   json += CHECK_JsonKvString("message_type", CHECK_MSG_MARKET, true);
   json += CHECK_JsonKvString("message_id", message_id, true);
   json += CHECK_JsonKvString("generated_at_utc", generated, true);
   json += CHECK_JsonKvString("source", CHECK_SOURCE_MT4, true);
   json += CHECK_JsonKvLong("sequence", sequence, true);
   json += CHECK_JsonKvString("account_number", IntegerToString(AccountNumber()), true);
   json += CHECK_JsonKvString("server", AccountServer(), true);
   json += CHECK_JsonKvString("symbol", symbol, true);
   json += CHECK_JsonKvInt("digits", digits, true);
   json += CHECK_JsonKvNumber("point", point, digits, true);
   json += CHECK_JsonKvNumber("pip_size", pip_size, digits, true);
   json += CHECK_JsonKvNumber("bid", bid, digits, true);
   json += CHECK_JsonKvNumber("ask", ask, digits, true);
   json += CHECK_JsonKvNumber("spread_points", spread_points, 1, true);
   json += CHECK_JsonKvNumber("spread_pips", spread_pips, 2, true);
   json += CHECK_JsonKvNumber("tick_size", tick_size, digits, true);
   json += CHECK_JsonKvNumber("tick_value", tick_value, 5, true);
   json += CHECK_JsonKvNumber("minimum_lot", min_lot, 2, true);
   json += CHECK_JsonKvNumber("maximum_lot", max_lot, 2, true);
   json += CHECK_JsonKvNumber("lot_step", lot_step, 2, true);
   json += CHECK_JsonKvInt("stop_level_points", stop_level, true);
   json += CHECK_JsonKvInt("freeze_level_points", freeze_level, true);
   json += CHECK_JsonKvBool("trade_allowed", IsTradeAllowed(), true);
   json += CHECK_JsonKvBool("market_open", CHECK_IsMarketOpen(symbol), true);
   json += "  \"bars_m1\": " + CHECK_BuildBarsM1Json(symbol) + "\n";
   json += "}\n";
   return json;
}

string CHECK_BuildPositionJsonFromSelected()
{
   string symbol = OrderSymbol();
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits <= 0)
      digits = 5;
   string side = (OrderType() == OP_BUY) ? CHECK_SIDE_BUY : CHECK_SIDE_SELL;
   double profit = OrderProfit();
   double swap = OrderSwap();
   double commission = OrderCommission();
   double net_profit = profit + swap + commission;
   double current_price = (OrderType() == OP_BUY)
      ? MarketInfo(symbol, MODE_BID)
      : MarketInfo(symbol, MODE_ASK);

   string json = "    {\n";
   json += "      \"ticket\": " + IntegerToString(OrderTicket()) + ",\n";
   json += "      \"symbol\": \"" + CHECK_EscapeJsonString(symbol) + "\",\n";
   json += "      \"magic\": " + IntegerToString(OrderMagicNumber()) + ",\n";
   json += "      \"side\": \"" + side + "\",\n";
   json += "      \"volume\": " + CHECK_FormatJsonNumber(OrderLots(), 2) + ",\n";
   json += "      \"open_time\": \"" + CHECK_FormatTimeUtc(OrderOpenTime()) + "\",\n";
   json += "      \"open_price\": " + CHECK_FormatJsonNumber(OrderOpenPrice(), digits) + ",\n";
   json += "      \"stop_loss\": " + CHECK_FormatJsonNumber(OrderStopLoss(), digits) + ",\n";
   json += "      \"take_profit\": " + CHECK_FormatJsonNumber(OrderTakeProfit(), digits) + ",\n";
   json += "      \"current_price\": " + CHECK_FormatJsonNumber(current_price, digits) + ",\n";
   json += "      \"profit\": " + CHECK_FormatJsonNumber(profit, 2) + ",\n";
   json += "      \"swap\": " + CHECK_FormatJsonNumber(swap, 2) + ",\n";
   json += "      \"commission\": " + CHECK_FormatJsonNumber(commission, 2) + ",\n";
   json += "      \"net_profit\": " + CHECK_FormatJsonNumber(net_profit, 2) + ",\n";
   json += "      \"comment\": \"" + CHECK_EscapeJsonString(OrderComment()) + "\"\n";
   json += "    }";
   return json;
}

string CHECK_BuildPositionsJson()
{
   string json = "[\n";
   int count = 0;
   for(int index = OrdersTotal() - 1; index >= 0; index--)
   {
      if(!OrderSelect(index, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL)
         continue;
      if(count > 0)
         json += ",\n";
      json += CHECK_BuildPositionJsonFromSelected();
      count++;
   }
   if(count == 0)
      return "[]";
   json += "\n  ]";
   return json;
}

string CHECK_BuildStatusSnapshotJson()
{
   long sequence = CHECK_NextSequence();
   string generated = CHECK_NowUtcIso();
   string message_id = CHECK_NewMessageId();
   double balance = AccountBalance();
   double equity = AccountEquity();
   double margin = AccountMargin();
   double free_margin = AccountFreeMargin();
   double margin_level = 0.0;
   if(margin > 0.0)
      margin_level = (equity / margin) * 100.0;

   string positions = CHECK_BuildPositionsJson();

   string json = "{\n";
   json += CHECK_JsonKvString("protocol_version", CHECK_PROTOCOL_VERSION, true);
   json += CHECK_JsonKvString("message_type", CHECK_MSG_STATUS, true);
   json += CHECK_JsonKvString("message_id", message_id, true);
   json += CHECK_JsonKvString("generated_at_utc", generated, true);
   json += CHECK_JsonKvString("source", CHECK_SOURCE_MT4, true);
   json += CHECK_JsonKvLong("sequence", sequence, true);
   json += CHECK_JsonKvString("account_number", IntegerToString(AccountNumber()), true);
   json += CHECK_JsonKvNumber("balance", balance, 2, true);
   json += CHECK_JsonKvNumber("equity", equity, 2, true);
   json += CHECK_JsonKvNumber("margin", margin, 2, true);
   json += CHECK_JsonKvNumber("free_margin", free_margin, 2, true);
   json += CHECK_JsonKvNumber("margin_level", margin_level, 2, true);
   json += CHECK_JsonKvBool("trade_allowed", IsTradeAllowed(), true);
   json += CHECK_JsonKvBool("expert_enabled", IsExpertEnabled(), true);
   json += "  \"positions\": " + positions + ",\n";
   // Alias for Python loader compatibility during transition.
   json += "  \"open_positions\": " + positions + "\n";
   json += "}\n";
   return json;
}

bool CHECK_ExportMarketSnapshot()
{
   string payload = CHECK_BuildMarketSnapshotJson();
   return CHECK_AtomicWriteText(CHECK_MarketFilePath(), payload);
}

bool CHECK_ExportStatusSnapshot()
{
   string payload = CHECK_BuildStatusSnapshotJson();
   return CHECK_AtomicWriteText(CHECK_StatusFilePath(), payload);
}

void CHECK_ExportMarketAndStatus()
{
   if(StringLen(g_check_bridge_root) == 0)
      return;

   uint now_ms = GetTickCount();
   uint elapsed = now_ms - g_check_last_export_ms;
   if(g_check_last_export_ms != 0 && elapsed < (uint)CHECK_EXPORT_INTERVAL_MS)
      return;

   if(!CHECK_EnsureBridgeDirectories())
   {
      Print("CHECK_SYSTEM_V2: failed to ensure bridge directories under ", g_check_bridge_root);
      return;
   }

   if(!CHECK_ExportMarketSnapshot())
      Print("CHECK_SYSTEM_V2: market snapshot export failed");
   if(!CHECK_ExportStatusSnapshot())
      Print("CHECK_SYSTEM_V2: status snapshot export failed");

   g_check_last_export_ms = now_ms;
}

#endif
