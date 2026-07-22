#ifndef __CHECK_EXECUTION_MQH__
#define __CHECK_EXECUTION_MQH__
#property strict

#include <CHECK_Protocol.mqh>
#include <CHECK_Json.mqh>

struct CHECK_Command
{
   string protocol_version;
   string message_type;
   string message_id;
   string generated_at_utc;
   string source;
   long   sequence;
   string command_id;
   string action;
   string symbol;
   int    magic;
   int    account_number;
   bool   has_account_number;
   string side;
   bool   has_side;
   double volume;
   bool   has_volume;
   int    ticket;
   bool   has_ticket;
   double requested_price;
   bool   has_requested_price;
   double stop_loss;
   bool   has_stop_loss;
   double take_profit;
   bool   has_take_profit;
   double requested_stop_loss;
   bool   has_requested_stop_loss;
   double requested_take_profit;
   bool   has_requested_take_profit;
   double previous_broker_stop_loss;
   bool   has_previous_broker_stop_loss;
   int    slippage_points;
   string setup_id;
   string setup_fingerprint;
   string trailing_reason;
   double trailing_step;
   string close_reason;
   string created_at_utc;
   string source_filename;
};

struct CHECK_AckResult
{
   string status;
   string action;
   int    ticket;
   bool   has_ticket;
   double requested_price;
   bool   has_requested_price;
   double applied_price;
   bool   has_applied_price;
   double requested_stop_loss;
   bool   has_requested_stop_loss;
   double applied_stop_loss;
   bool   has_applied_stop_loss;
   double requested_take_profit;
   bool   has_requested_take_profit;
   double applied_take_profit;
   bool   has_applied_take_profit;
   double requested_volume;
   bool   has_requested_volume;
   double applied_volume;
   bool   has_applied_volume;
   int    broker_error_code;
   string broker_error_text;
   string side;
};

void CHECK_ResetCommand(CHECK_Command &command)
{
   command.protocol_version = "";
   command.message_type = "";
   command.message_id = "";
   command.generated_at_utc = "";
   command.source = "";
   command.sequence = 0;
   command.command_id = "";
   command.action = "";
   command.symbol = "";
   command.magic = 0;
   command.account_number = 0;
   command.has_account_number = false;
   command.side = "";
   command.has_side = false;
   command.volume = 0.0;
   command.has_volume = false;
   command.ticket = 0;
   command.has_ticket = false;
   command.requested_price = 0.0;
   command.has_requested_price = false;
   command.stop_loss = 0.0;
   command.has_stop_loss = false;
   command.take_profit = 0.0;
   command.has_take_profit = false;
   command.requested_stop_loss = 0.0;
   command.has_requested_stop_loss = false;
   command.requested_take_profit = 0.0;
   command.has_requested_take_profit = false;
   command.previous_broker_stop_loss = 0.0;
   command.has_previous_broker_stop_loss = false;
   command.slippage_points = CHECK_DEFAULT_SLIPPAGE;
   command.setup_id = "";
   command.setup_fingerprint = "";
   command.trailing_reason = "";
   command.trailing_step = 0.0;
   command.close_reason = "";
   command.created_at_utc = "";
   command.source_filename = "";
}

void CHECK_ResetAckResult(CHECK_AckResult &result)
{
   result.status = "";
   result.action = "";
   result.ticket = 0;
   result.has_ticket = false;
   result.requested_price = 0.0;
   result.has_requested_price = false;
   result.applied_price = 0.0;
   result.has_applied_price = false;
   result.requested_stop_loss = 0.0;
   result.has_requested_stop_loss = false;
   result.applied_stop_loss = 0.0;
   result.has_applied_stop_loss = false;
   result.requested_take_profit = 0.0;
   result.has_requested_take_profit = false;
   result.applied_take_profit = 0.0;
   result.has_applied_take_profit = false;
   result.requested_volume = 0.0;
   result.has_requested_volume = false;
   result.applied_volume = 0.0;
   result.has_applied_volume = false;
   result.broker_error_code = 0;
   result.broker_error_text = "";
   result.side = "";
}

void CHECK_SetRejectedAck(CHECK_AckResult &result, const string message, const int error_code = 0)
{
   string action = result.action;
   double req_sl = result.requested_stop_loss;
   bool has_req_sl = result.has_requested_stop_loss;
   double req_tp = result.requested_take_profit;
   bool has_req_tp = result.has_requested_take_profit;
   double app_sl = result.applied_stop_loss;
   bool has_app_sl = result.has_applied_stop_loss;
   double app_tp = result.applied_take_profit;
   bool has_app_tp = result.has_applied_take_profit;
   double req_price = result.requested_price;
   bool has_req_price = result.has_requested_price;
   double req_vol = result.requested_volume;
   bool has_req_vol = result.has_requested_volume;
   int ticket = result.ticket;
   bool has_ticket = result.has_ticket;
   string side = result.side;

   CHECK_ResetAckResult(result);
   result.status = CHECK_ACK_REJECTED;
   result.action = action;
   result.broker_error_text = message;
   result.broker_error_code = error_code;
   result.requested_stop_loss = req_sl;
   result.has_requested_stop_loss = has_req_sl;
   result.requested_take_profit = req_tp;
   result.has_requested_take_profit = has_req_tp;
   result.applied_stop_loss = app_sl;
   result.has_applied_stop_loss = has_app_sl;
   result.applied_take_profit = app_tp;
   result.has_applied_take_profit = has_app_tp;
   result.requested_price = req_price;
   result.has_requested_price = has_req_price;
   result.requested_volume = req_vol;
   result.has_requested_volume = has_req_vol;
   result.ticket = ticket;
   result.has_ticket = has_ticket;
   result.side = side;
}

void CHECK_SetFailedAck(CHECK_AckResult &result, const string message, const int error_code)
{
   string action = result.action;
   double req_sl = result.requested_stop_loss;
   bool has_req_sl = result.has_requested_stop_loss;
   double req_tp = result.requested_take_profit;
   bool has_req_tp = result.has_requested_take_profit;
   double app_sl = result.applied_stop_loss;
   bool has_app_sl = result.has_applied_stop_loss;
   double app_tp = result.applied_take_profit;
   bool has_app_tp = result.has_applied_take_profit;
   double req_price = result.requested_price;
   bool has_req_price = result.has_requested_price;
   double app_price = result.applied_price;
   bool has_app_price = result.has_applied_price;
   double req_vol = result.requested_volume;
   bool has_req_vol = result.has_requested_volume;
   double app_vol = result.applied_volume;
   bool has_app_vol = result.has_applied_volume;
   int ticket = result.ticket;
   bool has_ticket = result.has_ticket;
   string side = result.side;

   CHECK_ResetAckResult(result);
   result.status = CHECK_ACK_FAILED;
   result.action = action;
   result.broker_error_text = message;
   result.broker_error_code = error_code;
   result.requested_stop_loss = req_sl;
   result.has_requested_stop_loss = has_req_sl;
   result.requested_take_profit = req_tp;
   result.has_requested_take_profit = has_req_tp;
   result.applied_stop_loss = app_sl;
   result.has_applied_stop_loss = has_app_sl;
   result.applied_take_profit = app_tp;
   result.has_applied_take_profit = has_app_tp;
   result.requested_price = req_price;
   result.has_requested_price = has_req_price;
   result.applied_price = app_price;
   result.has_applied_price = has_app_price;
   result.requested_volume = req_vol;
   result.has_requested_volume = has_req_vol;
   result.applied_volume = app_vol;
   result.has_applied_volume = has_app_vol;
   result.ticket = ticket;
   result.has_ticket = has_ticket;
   result.side = side;
}

bool CHECK_SlImprovesProtection(const int order_type, const double previous_sl, const double applied_sl, const double tolerance)
{
   if(previous_sl <= 0.0 && applied_sl > 0.0)
      return true;
   if(order_type == OP_BUY)
      return applied_sl > previous_sl + tolerance;
   if(order_type == OP_SELL)
      return applied_sl < previous_sl - tolerance;
   return false;
}

bool CHECK_ValidateAppliedStopLoss(const int order_type, const double previous_sl, const double requested_sl, const double applied_sl, const double tolerance)
{
   if(!CHECK_SlImprovesProtection(order_type, previous_sl, applied_sl, tolerance))
      return false;
   if(MathAbs(applied_sl - requested_sl) > tolerance)
      return false;
   return true;
}

bool CHECK_WouldWorsenStopLoss(const int order_type, const double previous_sl, const double requested_sl, const double tolerance)
{
   if(requested_sl <= 0.0)
      return true;
   if(previous_sl <= 0.0)
      return false;
   if(order_type == OP_BUY)
      return requested_sl < previous_sl - tolerance;
   if(order_type == OP_SELL)
      return requested_sl > previous_sl + tolerance;
   return true;
}

bool CHECK_ValidateStopDistance(const string symbol, const int order_type, const double price, const double stop_loss, const double take_profit, string &error_message)
{
   error_message = "";
   double point = MarketInfo(symbol, MODE_POINT);
   if(point <= 0.0)
      point = 0.00001;
   int stop_level = (int)MarketInfo(symbol, MODE_STOPLEVEL);
   int freeze_level = (int)MarketInfo(symbol, MODE_FREEZELEVEL);
   int min_points = MathMax(stop_level, freeze_level);
   double min_distance = min_points * point;

   if(stop_loss > 0.0)
   {
      double sl_distance = MathAbs(price - stop_loss);
      if(sl_distance + 1e-12 < min_distance)
      {
         error_message = "stop_loss inside stop/freeze level";
         return false;
      }
      if(order_type == OP_BUY && stop_loss >= price)
      {
         error_message = "BUY stop_loss must be below price";
         return false;
      }
      if(order_type == OP_SELL && stop_loss <= price)
      {
         error_message = "SELL stop_loss must be above price";
         return false;
      }
   }
   if(take_profit > 0.0)
   {
      double tp_distance = MathAbs(price - take_profit);
      if(tp_distance + 1e-12 < min_distance)
      {
         error_message = "take_profit inside stop/freeze level";
         return false;
      }
      if(order_type == OP_BUY && take_profit <= price)
      {
         error_message = "BUY take_profit must be above price";
         return false;
      }
      if(order_type == OP_SELL && take_profit >= price)
      {
         error_message = "SELL take_profit must be below price";
         return false;
      }
   }
   return true;
}

bool CHECK_ValidateLot(const string symbol, const double volume, string &error_message)
{
   error_message = "";
   double min_lot = MarketInfo(symbol, MODE_MINLOT);
   double max_lot = MarketInfo(symbol, MODE_MAXLOT);
   double step = MarketInfo(symbol, MODE_LOTSTEP);
   if(volume + 1e-12 < min_lot)
   {
      error_message = "volume below minimum_lot";
      return false;
   }
   if(max_lot > 0.0 && volume - 1e-12 > max_lot)
   {
      error_message = "volume above maximum_lot";
      return false;
   }
   if(step > 0.0)
   {
      double steps = volume / step;
      if(MathAbs(steps - MathRound(steps)) > 1e-6)
      {
         error_message = "volume not aligned to lot_step";
         return false;
      }
   }
   return true;
}

bool CHECK_SelectOrderByTicket(const int ticket, const string symbol, const int magic)
{
   if(ticket <= 0)
      return false;
   if(!OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES))
      return false;
   if(OrderSymbol() != symbol)
      return false;
   if(OrderMagicNumber() != magic)
      return false;
   if(OrderType() != OP_BUY && OrderType() != OP_SELL)
      return false;
   return true;
}

bool CHECK_OrderExistsInHistory(const int ticket, const string symbol, const int magic)
{
   if(ticket <= 0)
      return false;
   for(int index = OrdersHistoryTotal() - 1; index >= 0; index--)
   {
      if(!OrderSelect(index, SELECT_BY_POS, MODE_HISTORY))
         continue;
      if(OrderTicket() != ticket)
         continue;
      if(OrderSymbol() != symbol)
         continue;
      if(OrderMagicNumber() != magic)
         continue;
      if(OrderCloseTime() > 0)
         return true;
   }
   return false;
}

string CHECK_UIntToHex8(const uint value)
{
   string digits = "0123456789abcdef";
   string hex = "";
   for(int i = 0; i < 8; i++)
   {
      int nibble = (int)((value >> (28 - i * 4)) & 0xF);
      hex = hex + StringSubstr(digits, nibble, 1);
   }
   return hex;
}

string CHECK_BuildOpenOrderComment(const string command_id)
{
   int length = StringLen(command_id);
   if(length > 0 && length <= 31)
      return command_id;
   uint hash = 5381;
   for(int index = 0; index < length; index++)
      hash = hash * 33 + (uint)StringGetCharacter(command_id, index);
   return "C" + CHECK_UIntToHex8(hash);
}

bool CHECK_ParseCommandJson(const string json, CHECK_Command &command, string &error_message)
{
   CHECK_ResetCommand(command);
   error_message = "";

   if(StringLen(json) == 0)
   {
      error_message = "command json is empty";
      return false;
   }

   CHECK_ExtractJsonStringField(json, "protocol_version", command.protocol_version);
   CHECK_ExtractJsonStringField(json, "message_type", command.message_type);
   CHECK_ExtractJsonStringField(json, "message_id", command.message_id);
   CHECK_ExtractJsonStringField(json, "generated_at_utc", command.generated_at_utc);
   CHECK_ExtractJsonStringField(json, "source", command.source);
   CHECK_ExtractJsonLongField(json, "sequence", command.sequence);

   if(!CHECK_ExtractJsonStringField(json, "command_id", command.command_id))
   {
      error_message = "missing command_id";
      return false;
   }
   if(!CHECK_ExtractJsonStringField(json, "action", command.action))
   {
      error_message = "missing action";
      return false;
   }
   if(!CHECK_ExtractJsonStringField(json, "symbol", command.symbol))
   {
      error_message = "missing symbol";
      return false;
   }
   if(!CHECK_ExtractJsonIntField(json, "magic", command.magic))
   {
      error_message = "missing magic";
      return false;
   }

   int account_number = 0;
   if(CHECK_ExtractJsonIntField(json, "account_number", account_number))
   {
      command.account_number = account_number;
      command.has_account_number = true;
   }
   else
   {
      string account_str = "";
      if(CHECK_ExtractJsonStringField(json, "account_number", account_str))
      {
         command.account_number = (int)StringToInteger(account_str);
         command.has_account_number = true;
      }
   }

   string side = "";
   if(CHECK_ExtractJsonStringField(json, "side", side))
   {
      command.side = side;
      command.has_side = true;
   }
   double volume = 0.0;
   if(CHECK_ExtractJsonDoubleField(json, "volume", volume))
   {
      command.volume = volume;
      command.has_volume = true;
   }
   int ticket = 0;
   if(CHECK_ExtractJsonIntField(json, "ticket", ticket))
   {
      command.ticket = ticket;
      command.has_ticket = true;
   }
   double requested_price = 0.0;
   if(CHECK_ExtractJsonDoubleField(json, "requested_price", requested_price))
   {
      command.requested_price = requested_price;
      command.has_requested_price = true;
   }
   double stop_loss = 0.0;
   if(CHECK_ExtractJsonDoubleField(json, "stop_loss", stop_loss))
   {
      command.stop_loss = stop_loss;
      command.has_stop_loss = true;
   }
   double take_profit = 0.0;
   if(CHECK_ExtractJsonDoubleField(json, "take_profit", take_profit))
   {
      command.take_profit = take_profit;
      command.has_take_profit = true;
   }
   double requested_stop_loss = 0.0;
   if(CHECK_ExtractJsonDoubleField(json, "requested_stop_loss", requested_stop_loss))
   {
      command.requested_stop_loss = requested_stop_loss;
      command.has_requested_stop_loss = true;
   }
   double requested_take_profit = 0.0;
   if(CHECK_ExtractJsonDoubleField(json, "requested_take_profit", requested_take_profit))
   {
      command.requested_take_profit = requested_take_profit;
      command.has_requested_take_profit = true;
   }
   double previous_broker_stop_loss = 0.0;
   if(CHECK_ExtractJsonDoubleField(json, "previous_broker_stop_loss", previous_broker_stop_loss))
   {
      command.previous_broker_stop_loss = previous_broker_stop_loss;
      command.has_previous_broker_stop_loss = true;
   }
   int slippage = CHECK_DEFAULT_SLIPPAGE;
   if(CHECK_ExtractJsonIntField(json, "slippage_points", slippage))
      command.slippage_points = slippage;

   CHECK_ExtractJsonStringField(json, "setup_id", command.setup_id);
   CHECK_ExtractJsonStringField(json, "setup_fingerprint", command.setup_fingerprint);
   CHECK_ExtractJsonStringField(json, "trailing_reason", command.trailing_reason);
   CHECK_ExtractJsonDoubleField(json, "trailing_step", command.trailing_step);
   CHECK_ExtractJsonStringField(json, "close_reason", command.close_reason);
   CHECK_ExtractJsonStringField(json, "created_at_utc", command.created_at_utc);

   if(command.action != CHECK_ACTION_OPEN
      && command.action != CHECK_ACTION_MODIFY
      && command.action != CHECK_ACTION_CLOSE)
   {
      error_message = "unsupported action";
      return false;
   }
   return true;
}

bool CHECK_ValidateCommandInstance(const CHECK_Command &command, string &error_message)
{
   error_message = "";
   if(command.has_account_number && command.account_number != AccountNumber())
   {
      error_message = "account_number does not match terminal account";
      return false;
   }
   if(command.symbol != g_check_symbol)
   {
      error_message = "symbol does not match EA chart symbol";
      return false;
   }
   if(command.magic != g_check_magic)
   {
      error_message = "magic does not match EA MagicNumber";
      return false;
   }
   return true;
}

string CHECK_BuildAckJson(const CHECK_Command &command, const CHECK_AckResult &result)
{
   int digits = (int)MarketInfo(command.symbol, MODE_DIGITS);
   if(digits <= 0)
      digits = 5;
   long sequence = command.sequence;
   if(sequence <= 0)
      sequence = g_check_sequence;

   string json = "{\n";
   json += CHECK_JsonKvString("protocol_version", CHECK_PROTOCOL_VERSION, true);
   json += CHECK_JsonKvString("message_type", CHECK_MSG_ACK, true);
   json += CHECK_JsonKvString("message_id", CHECK_NewMessageId(), true);
   json += CHECK_JsonKvString("generated_at_utc", CHECK_NowUtcIso(), true);
   json += CHECK_JsonKvString("processed_at_utc", CHECK_NowUtcIso(), true);
   json += CHECK_JsonKvString("source", CHECK_SOURCE_MT4, true);
   json += CHECK_JsonKvLong("sequence", sequence, true);
   json += CHECK_JsonKvString("command_id", command.command_id, true);
   json += CHECK_JsonKvString("action", (StringLen(result.action) > 0 ? result.action : command.action), true);
   json += CHECK_JsonKvString("status", result.status, true);
   json += CHECK_JsonKvString("symbol", command.symbol, true);
   json += CHECK_JsonKvInt("magic", command.magic, true);
   json += CHECK_JsonKvString("account_number", IntegerToString(AccountNumber()), true);

   if(result.has_ticket)
      json += CHECK_JsonKvInt("ticket", result.ticket, true);
   if(StringLen(result.side) > 0)
      json += CHECK_JsonKvString("side", result.side, true);
   if(result.has_requested_price)
      json += CHECK_JsonKvNumber("requested_price", result.requested_price, digits, true);
   if(result.has_applied_price)
      json += CHECK_JsonKvNumber("applied_price", result.applied_price, digits, true);
   if(result.has_requested_volume)
      json += CHECK_JsonKvNumber("requested_volume", result.requested_volume, 2, true);
   if(result.has_applied_volume)
      json += CHECK_JsonKvNumber("applied_volume", result.applied_volume, 2, true);
   if(result.has_requested_stop_loss)
      json += CHECK_JsonKvNumber("requested_stop_loss", result.requested_stop_loss, digits, true);
   if(result.has_applied_stop_loss)
      json += CHECK_JsonKvNumber("applied_stop_loss", result.applied_stop_loss, digits, true);
   if(result.has_requested_take_profit)
      json += CHECK_JsonKvNumber("requested_take_profit", result.requested_take_profit, digits, true);
   if(result.has_applied_take_profit)
      json += CHECK_JsonKvNumber("applied_take_profit", result.applied_take_profit, digits, true);

   json += CHECK_JsonKvInt("broker_error_code", result.broker_error_code, true);
   json += CHECK_JsonKvString("broker_error_text", result.broker_error_text, false);
   json += "}\n";
   return json;
}

bool CHECK_WriteAck(const CHECK_Command &command, const CHECK_AckResult &result)
{
   if(StringLen(command.command_id) == 0)
      return false;
   if(!CHECK_EnsureBridgeDirectories())
      return false;

   long sequence = command.sequence;
   if(sequence <= 0)
      sequence = g_check_sequence;
   string filename = IntegerToString((int)sequence) + "_" + command.command_id + ".ack.json";
   string path = CHECK_JoinPath(CHECK_AcksDir(), filename);
   return CHECK_AtomicWriteText(path, CHECK_BuildAckJson(command, result));
}

bool CHECK_ArchiveCommandFile(const CHECK_Command &command)
{
   if(StringLen(command.source_filename) == 0)
      return true;
   string from_path = CHECK_JoinPath(CHECK_CommandsDir(), command.source_filename);
   if(!CHECK_FileExistsAbs(from_path))
      return true;
   string to_path = CHECK_JoinPath(CHECK_JoinPath(CHECK_ArchiveDir(), CHECK_DIR_COMMANDS), command.source_filename);
   return CHECK_MoveFileAbs(from_path, to_path);
}

bool CHECK_ExecuteOpen(const CHECK_Command &command, CHECK_AckResult &result, string &error_message)
{
   CHECK_ResetAckResult(result);
   result.action = CHECK_ACTION_OPEN;
   error_message = "";

   if(!command.has_side || (command.side != CHECK_SIDE_BUY && command.side != CHECK_SIDE_SELL))
   {
      CHECK_SetRejectedAck(result, "OPEN requires side BUY or SELL");
      error_message = result.broker_error_text;
      return false;
   }
   if(!command.has_volume || command.volume <= 0.0)
   {
      CHECK_SetRejectedAck(result, "OPEN requires positive volume");
      error_message = result.broker_error_text;
      return false;
   }
   if(!IsTradeAllowed())
   {
      CHECK_SetRejectedAck(result, "trade is not allowed");
      error_message = result.broker_error_text;
      return false;
   }
   if(!IsExpertEnabled())
   {
      CHECK_SetRejectedAck(result, "expert advisors disabled");
      error_message = result.broker_error_text;
      return false;
   }

   int trade_command = (command.side == CHECK_SIDE_BUY) ? OP_BUY : OP_SELL;
   double price = (trade_command == OP_BUY)
      ? MarketInfo(command.symbol, MODE_ASK)
      : MarketInfo(command.symbol, MODE_BID);
   price = CHECK_NormalizePrice(command.symbol, price);

   double stop_loss = command.has_stop_loss ? CHECK_NormalizePrice(command.symbol, command.stop_loss) : 0.0;
   double take_profit = command.has_take_profit ? CHECK_NormalizePrice(command.symbol, command.take_profit) : 0.0;
   double volume = CHECK_NormalizeLot(command.symbol, command.volume);

   result.requested_price = command.has_requested_price ? command.requested_price : price;
   result.has_requested_price = true;
   result.requested_volume = command.volume;
   result.has_requested_volume = true;
   result.requested_stop_loss = stop_loss;
   result.has_requested_stop_loss = true;
   result.requested_take_profit = take_profit;
   result.has_requested_take_profit = true;
   result.side = command.side;

   string lot_error = "";
   if(!CHECK_ValidateLot(command.symbol, volume, lot_error))
   {
      CHECK_SetRejectedAck(result, lot_error);
      error_message = result.broker_error_text;
      return false;
   }

   string stop_error = "";
   if(!CHECK_ValidateStopDistance(command.symbol, trade_command, price, stop_loss, take_profit, stop_error))
   {
      CHECK_SetRejectedAck(result, stop_error);
      error_message = result.broker_error_text;
      return false;
   }

   double required_margin = AccountFreeMarginCheck(command.symbol, trade_command, volume);
   if(required_margin < 0.0)
   {
      CHECK_SetRejectedAck(result, "insufficient margin for OPEN", GetLastError());
      error_message = result.broker_error_text;
      return false;
   }

   RefreshRates();
   price = (trade_command == OP_BUY)
      ? MarketInfo(command.symbol, MODE_ASK)
      : MarketInfo(command.symbol, MODE_BID);
   price = CHECK_NormalizePrice(command.symbol, price);

   int slippage = command.slippage_points;
   if(slippage <= 0)
      slippage = CHECK_DEFAULT_SLIPPAGE;
   string comment = CHECK_BuildOpenOrderComment(command.command_id);

   ResetLastError();
   int ticket = OrderSend(
      command.symbol,
      trade_command,
      volume,
      price,
      slippage,
      stop_loss,
      take_profit,
      comment,
      command.magic,
      0,
      clrNONE
   );
   if(ticket < 0)
   {
      int error_code = GetLastError();
      CHECK_SetFailedAck(result, "OrderSend failed", error_code);
      error_message = result.broker_error_text;
      return false;
   }

   if(OrderSelect(ticket, SELECT_BY_TICKET, MODE_TRADES))
   {
      result.status = CHECK_ACK_SUCCESS;
      result.ticket = ticket;
      result.has_ticket = true;
      result.applied_price = OrderOpenPrice();
      result.has_applied_price = true;
      result.applied_volume = OrderLots();
      result.has_applied_volume = true;
      result.applied_stop_loss = OrderStopLoss();
      result.has_applied_stop_loss = true;
      result.applied_take_profit = OrderTakeProfit();
      result.has_applied_take_profit = true;
      result.side = (OrderType() == OP_BUY) ? CHECK_SIDE_BUY : CHECK_SIDE_SELL;
      result.broker_error_code = 0;
      result.broker_error_text = "";
   }
   else
   {
      result.status = CHECK_ACK_SUCCESS;
      result.ticket = ticket;
      result.has_ticket = true;
      result.applied_price = price;
      result.has_applied_price = true;
      result.applied_volume = volume;
      result.has_applied_volume = true;
      result.broker_error_text = "OrderSend ok but reselect failed";
   }
   return true;
}

bool CHECK_ExecuteModify(const CHECK_Command &command, CHECK_AckResult &result, string &error_message)
{
   CHECK_ResetAckResult(result);
   result.action = CHECK_ACTION_MODIFY;
   error_message = "";

   if(command.has_requested_stop_loss)
   {
      result.requested_stop_loss = CHECK_NormalizePrice(command.symbol, command.requested_stop_loss);
      result.has_requested_stop_loss = true;
   }
   if(command.has_requested_take_profit)
   {
      result.requested_take_profit = CHECK_NormalizePrice(command.symbol, command.requested_take_profit);
      result.has_requested_take_profit = true;
   }

   if(!command.has_ticket || command.ticket <= 0)
   {
      // MODIFY ACKs always expose requested/applied SL fields.
      result.applied_stop_loss = 0.0;
      result.has_applied_stop_loss = true;
      CHECK_SetRejectedAck(result, "MODIFY requires ticket");
      error_message = result.broker_error_text;
      return false;
   }
   if(!CHECK_SelectOrderByTicket(command.ticket, command.symbol, command.magic))
   {
      result.ticket = command.ticket;
      result.has_ticket = true;
      result.applied_stop_loss = 0.0;
      result.has_applied_stop_loss = true;
      CHECK_SetRejectedAck(result, "MODIFY ticket not found for symbol/magic");
      error_message = result.broker_error_text;
      return false;
   }

   int order_type = OrderType();
   double previous_sl = OrderStopLoss();
   double previous_tp = OrderTakeProfit();
   double open_price = OrderOpenPrice();

   double requested_sl = command.has_requested_stop_loss
      ? CHECK_NormalizePrice(command.symbol, command.requested_stop_loss)
      : previous_sl;
   double requested_tp = command.has_requested_take_profit
      ? CHECK_NormalizePrice(command.symbol, command.requested_take_profit)
      : previous_tp;

   result.ticket = command.ticket;
   result.has_ticket = true;
   result.requested_stop_loss = requested_sl;
   result.has_requested_stop_loss = true;
   result.requested_take_profit = requested_tp;
   result.has_requested_take_profit = true;
   result.side = (order_type == OP_BUY) ? CHECK_SIDE_BUY : CHECK_SIDE_SELL;

   double tolerance = CHECK_PriceTolerance(command.symbol);
   if(CHECK_WouldWorsenStopLoss(order_type, previous_sl, requested_sl, tolerance))
   {
      result.applied_stop_loss = previous_sl;
      result.has_applied_stop_loss = true;
      result.applied_take_profit = previous_tp;
      result.has_applied_take_profit = true;
      CHECK_SetRejectedAck(result, "MODIFY would worsen stop loss protection");
      error_message = result.broker_error_text;
      return false;
   }

   double mark_price = (order_type == OP_BUY)
      ? MarketInfo(command.symbol, MODE_BID)
      : MarketInfo(command.symbol, MODE_ASK);
   string stop_error = "";
   if(!CHECK_ValidateStopDistance(command.symbol, order_type, mark_price, requested_sl, requested_tp, stop_error))
   {
      result.applied_stop_loss = previous_sl;
      result.has_applied_stop_loss = true;
      result.applied_take_profit = previous_tp;
      result.has_applied_take_profit = true;
      CHECK_SetRejectedAck(result, stop_error);
      error_message = result.broker_error_text;
      return false;
   }

   ResetLastError();
   bool modified = OrderModify(command.ticket, open_price, requested_sl, requested_tp, 0, clrNONE);
   if(!modified)
   {
      int error_code = GetLastError();
      result.applied_stop_loss = previous_sl;
      result.has_applied_stop_loss = true;
      result.applied_take_profit = previous_tp;
      result.has_applied_take_profit = true;
      CHECK_SetFailedAck(result, "OrderModify failed", error_code);
      error_message = result.broker_error_text;
      return false;
   }

   if(!CHECK_SelectOrderByTicket(command.ticket, command.symbol, command.magic))
   {
      CHECK_SetFailedAck(result, "OrderModify succeeded but reselect failed", GetLastError());
      error_message = result.broker_error_text;
      return false;
   }

   double applied_sl = OrderStopLoss();
   double applied_tp = OrderTakeProfit();
   result.applied_stop_loss = applied_sl;
   result.has_applied_stop_loss = true;
   result.applied_take_profit = applied_tp;
   result.has_applied_take_profit = true;

   if(!CHECK_ValidateAppliedStopLoss(order_type, previous_sl, requested_sl, applied_sl, tolerance))
   {
      CHECK_SetFailedAck(result, "applied stop loss failed protection/tolerance check", 0);
      error_message = result.broker_error_text;
      return false;
   }

   result.status = CHECK_ACK_SUCCESS;
   result.broker_error_code = 0;
   result.broker_error_text = "";
   return true;
}

bool CHECK_ExecuteClose(const CHECK_Command &command, CHECK_AckResult &result, string &error_message)
{
   CHECK_ResetAckResult(result);
   result.action = CHECK_ACTION_CLOSE;
   error_message = "";

   if(!command.has_ticket || command.ticket <= 0)
   {
      CHECK_SetRejectedAck(result, "CLOSE requires ticket");
      error_message = result.broker_error_text;
      return false;
   }

   // Already closed => reconciliation ACK, do not blind-close again.
   if(!CHECK_SelectOrderByTicket(command.ticket, command.symbol, command.magic))
   {
      if(CHECK_OrderExistsInHistory(command.ticket, command.symbol, command.magic))
      {
         result.status = CHECK_ACK_SUCCESS;
         result.ticket = command.ticket;
         result.has_ticket = true;
         result.broker_error_code = 0;
         result.broker_error_text = "already closed (reconciled)";
         if(command.has_volume)
         {
            result.requested_volume = command.volume;
            result.has_requested_volume = true;
            result.applied_volume = command.volume;
            result.has_applied_volume = true;
         }
         if(command.has_requested_price)
         {
            result.requested_price = command.requested_price;
            result.has_requested_price = true;
            result.applied_price = command.requested_price;
            result.has_applied_price = true;
         }
         return true;
      }
      CHECK_SetRejectedAck(result, "CLOSE ticket not found for symbol/magic");
      error_message = result.broker_error_text;
      return false;
   }

   int order_type = OrderType();
   double close_volume = command.has_volume ? CHECK_NormalizeLot(command.symbol, command.volume) : OrderLots();
   if(close_volume <= 0.0 || close_volume > OrderLots() + 1e-8)
      close_volume = OrderLots();

   RefreshRates();
   double close_price = (order_type == OP_BUY)
      ? MarketInfo(command.symbol, MODE_BID)
      : MarketInfo(command.symbol, MODE_ASK);
   close_price = CHECK_NormalizePrice(command.symbol, close_price);

   result.ticket = command.ticket;
   result.has_ticket = true;
   result.requested_volume = command.has_volume ? command.volume : close_volume;
   result.has_requested_volume = true;
   result.requested_price = command.has_requested_price ? command.requested_price : close_price;
   result.has_requested_price = true;
   result.side = (order_type == OP_BUY) ? CHECK_SIDE_BUY : CHECK_SIDE_SELL;

   int slippage = command.slippage_points;
   if(slippage <= 0)
      slippage = CHECK_DEFAULT_SLIPPAGE;

   ResetLastError();
   bool closed = OrderClose(command.ticket, close_volume, close_price, slippage, clrNONE);
   if(!closed)
   {
      int error_code = GetLastError();
      // Race: may have been closed by SL/TP between select and close.
      if(!CHECK_SelectOrderByTicket(command.ticket, command.symbol, command.magic)
         && CHECK_OrderExistsInHistory(command.ticket, command.symbol, command.magic))
      {
         result.status = CHECK_ACK_SUCCESS;
         result.broker_error_code = 0;
         result.broker_error_text = "already closed (reconciled after OrderClose fail)";
         result.applied_price = close_price;
         result.has_applied_price = true;
         result.applied_volume = close_volume;
         result.has_applied_volume = true;
         return true;
      }
      CHECK_SetFailedAck(result, "OrderClose failed", error_code);
      error_message = result.broker_error_text;
      return false;
   }

   if(CHECK_SelectOrderByTicket(command.ticket, command.symbol, command.magic))
   {
      CHECK_SetFailedAck(result, "OrderClose reported success but order still open", GetLastError());
      error_message = result.broker_error_text;
      return false;
   }

   result.status = CHECK_ACK_SUCCESS;
   result.applied_price = close_price;
   result.has_applied_price = true;
   result.applied_volume = close_volume;
   result.has_applied_volume = true;
   result.broker_error_code = 0;
   result.broker_error_text = "";
   return true;
}

bool CHECK_ExecuteCommand(const CHECK_Command &command, CHECK_AckResult &result, string &error_message)
{
   if(command.action == CHECK_ACTION_OPEN)
      return CHECK_ExecuteOpen(command, result, error_message);
   if(command.action == CHECK_ACTION_MODIFY)
      return CHECK_ExecuteModify(command, result, error_message);
   if(command.action == CHECK_ACTION_CLOSE)
      return CHECK_ExecuteClose(command, result, error_message);
   CHECK_ResetAckResult(result);
   result.action = command.action;
   CHECK_SetRejectedAck(result, "unsupported action");
   error_message = result.broker_error_text;
   return false;
}

bool CHECK_CommandFileLooksReady(const string path)
{
   if(!CHECK_FileExistsAbs(path))
      return false;
   if(CHECK_FileExistsAbs(CHECK_TmpPathFor(path)))
      return false;
   return true;
}

void CHECK_TryExecutePendingCommands()
{
   if(StringLen(g_check_bridge_root) == 0)
      return;
   if(!CHECK_EnsureBridgeDirectories())
      return;

   string names[];
   int count = CHECK_ListJsonFiles(CHECK_CommandsDir(), names);
   if(count <= 0)
      return;

   for(int i = 0; i < count; i++)
   {
      string filename = names[i];
      // Expect {sequence}_{command_id}.json
      if(StringFind(filename, "_", 0) < 0)
         continue;
      if(StringFind(filename, ".ack.json", 0) >= 0)
         continue;

      string path = CHECK_JoinPath(CHECK_CommandsDir(), filename);
      if(!CHECK_CommandFileLooksReady(path))
         continue;

      string json = "";
      if(!CHECK_ReadTextFile(path, json))
         continue;

      CHECK_Command command;
      string error_message = "";
      if(!CHECK_ParseCommandJson(json, command, error_message))
      {
         Print("CHECK_SYSTEM_V2: skip command parse error: ", error_message, " file=", filename);
         continue;
      }
      command.source_filename = filename;

      CHECK_AckResult result;
      CHECK_ResetAckResult(result);
      result.action = command.action;

      if(CHECK_IsCommandIdProcessed(command.command_id))
      {
         result.status = CHECK_ACK_ALREADY;
         result.broker_error_text = "command_id already processed";
         CHECK_WriteAck(command, result);
         CHECK_ArchiveCommandFile(command);
         continue;
      }

      if(!CHECK_ValidateCommandInstance(command, error_message))
      {
         CHECK_SetRejectedAck(result, error_message);
         CHECK_WriteAck(command, result);
         CHECK_MarkCommandIdProcessed(command.command_id);
         CHECK_ArchiveCommandFile(command);
         continue;
      }

      CHECK_ExecuteCommand(command, result, error_message);
      CHECK_WriteAck(command, result);
      CHECK_MarkCommandIdProcessed(command.command_id);
      CHECK_ArchiveCommandFile(command);
   }
}

#endif
