#ifndef __SYSTEM_CONTROL_MQH__
#define __SYSTEM_CONTROL_MQH__

#property strict

#include "SYSTEM_Status.mqh"

#define SYSTEM_CONTROL_FILENAME_TEMPLATE "control_%s_%d.json"
#define SYSTEM_ACTION_OPEN "OPEN"
#define SYSTEM_ACTION_MODIFY "MODIFY"
#define SYSTEM_ACTION_CLOSE "CLOSE"
#define SYSTEM_ACTION_NONE "NONE"

struct SYSTEM_ControlCommand
{
   string schema_version;
   string timestamp_utc;
   string command_id;
   string account_id;
   string symbol;
   int magic;
   string action;
   string reason;
   string decision_id;
   string side;
   double volume;
   double stop_loss;
   double take_profit;
   int ticket;
   string order_comment;
   bool has_side;
   bool has_volume;
   bool has_stop_loss;
   bool has_take_profit;
   bool has_ticket;
   bool has_order_comment;
};

void SYSTEM_ResetControlCommand(SYSTEM_ControlCommand &command)
{
   command.schema_version = "";
   command.timestamp_utc = "";
   command.command_id = "";
   command.account_id = "";
   command.symbol = "";
   command.magic = 0;
   command.action = "";
   command.reason = "";
   command.decision_id = "";
   command.side = "";
   command.volume = 0.0;
   command.stop_loss = 0.0;
   command.take_profit = 0.0;
   command.ticket = 0;
   command.order_comment = "";
   command.has_side = false;
   command.has_volume = false;
   command.has_stop_loss = false;
   command.has_take_profit = false;
   command.has_ticket = false;
   command.has_order_comment = false;
}

string SYSTEM_BuildControlFilePath(const string account_id, const string symbol, const int magic)
{
   string filename = StringFormat(SYSTEM_CONTROL_FILENAME_TEMPLATE, symbol, magic);
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), filename);
}

bool SYSTEM_IsControlTmpPresent(const string path)
{
   return SYSTEM_FileExists(SYSTEM_TmpPathFor(path));
}

bool SYSTEM_IsControlReady(const string path)
{
   if(SYSTEM_IsControlTmpPresent(path))
      return false;
   return SYSTEM_FileExists(path);
}

bool SYSTEM_ExtractJsonStringField(const string json, const string field_name, string &out_value)
{
   string needle = "\"" + field_name + "\":";
   int position = StringFind(json, needle, 0);
   if(position < 0)
      return false;

   position += StringLen(needle);
   while(position < StringLen(json) && StringGetCharacter(json, position) == ' ')
      position++;

   if(position >= StringLen(json) || StringGetCharacter(json, position) != '"')
      return false;

   position++;
   string value = "";
   bool escaped = false;
   while(position < StringLen(json))
   {
      int ch = StringGetCharacter(json, position);
      if(escaped)
      {
         if(ch == '"' || ch == '\\' || ch == '/')
            value += CharToString((uchar)ch);
         else if(ch == 'n')
            value += "\n";
         else if(ch == 'r')
            value += "\r";
         else if(ch == 't')
            value += "\t";
         else
            value += CharToString((uchar)ch);
         escaped = false;
         position++;
         continue;
      }
      if(ch == '\\')
      {
         escaped = true;
         position++;
         continue;
      }
      if(ch == '"')
      {
         out_value = value;
         return true;
      }
      value += CharToString((uchar)ch);
      position++;
   }
   return false;
}

bool SYSTEM_ExtractJsonToken(const string json, const string field_name, string &out_token)
{
   string needle = "\"" + field_name + "\":";
   int position = StringFind(json, needle, 0);
   if(position < 0)
      return false;

   position += StringLen(needle);
   while(position < StringLen(json) && StringGetCharacter(json, position) == ' ')
      position++;

   int end = position;
   while(end < StringLen(json))
   {
      int character = StringGetCharacter(json, end);
      if(character == ',' || character == '}' || character == '\n' || character == '\r')
         break;
      end++;
   }

   out_token = StringSubstr(json, position, end - position);
   StringTrimLeft(out_token);
   StringTrimRight(out_token);
   return StringLen(out_token) > 0;
}

bool SYSTEM_ExtractJsonIntField(const string json, const string field_name, int &out_value)
{
   string token = "";
   if(!SYSTEM_ExtractJsonToken(json, field_name, token))
      return false;

   out_value = (int)StringToInteger(token);
   return true;
}

bool SYSTEM_ExtractJsonDoubleField(const string json, const string field_name, double &out_value)
{
   string token = "";
   if(!SYSTEM_ExtractJsonToken(json, field_name, token))
      return false;

   out_value = StringToDouble(token);
   return true;
}

bool SYSTEM_IsSupportedOrderAction(const string action)
{
   return action == SYSTEM_ACTION_OPEN
      || action == SYSTEM_ACTION_MODIFY
      || action == SYSTEM_ACTION_CLOSE
      || action == SYSTEM_ACTION_NONE;
}

bool SYSTEM_ControlRequiresOrderExecution(const string action)
{
   return action == SYSTEM_ACTION_OPEN
      || action == SYSTEM_ACTION_MODIFY
      || action == SYSTEM_ACTION_CLOSE;
}

bool SYSTEM_ParseControlCommand(const string json, SYSTEM_ControlCommand &command, string &error_message)
{
   SYSTEM_ResetControlCommand(command);
   error_message = "";

   if(StringLen(json) == 0)
   {
      error_message = "control json is empty";
      return false;
   }

   if(!SYSTEM_ExtractJsonStringField(json, "schema_version", command.schema_version))
   {
      error_message = "missing schema_version";
      return false;
   }
   if(command.schema_version != SYSTEM_PROTOCOL_SCHEMA_VERSION)
   {
      error_message = "unsupported schema_version";
      return false;
   }
   if(!SYSTEM_ExtractJsonStringField(json, "timestamp_utc", command.timestamp_utc))
   {
      error_message = "missing timestamp_utc";
      return false;
   }
   if(!SYSTEM_ExtractJsonStringField(json, "command_id", command.command_id))
   {
      error_message = "missing command_id";
      return false;
   }
   if(!SYSTEM_ExtractJsonStringField(json, "account_id", command.account_id))
   {
      error_message = "missing account_id";
      return false;
   }
   if(!SYSTEM_ExtractJsonStringField(json, "symbol", command.symbol))
   {
      error_message = "missing symbol";
      return false;
   }
   if(!SYSTEM_ExtractJsonIntField(json, "magic", command.magic))
   {
      error_message = "missing magic";
      return false;
   }
   if(!SYSTEM_ExtractJsonStringField(json, "action", command.action))
   {
      error_message = "missing action";
      return false;
   }
   if(!SYSTEM_IsSupportedOrderAction(command.action))
   {
      error_message = "invalid action";
      return false;
   }
   if(!SYSTEM_ExtractJsonStringField(json, "reason", command.reason))
   {
      error_message = "missing reason";
      return false;
   }
   if(!SYSTEM_ExtractJsonStringField(json, "decision_id", command.decision_id))
   {
      error_message = "missing decision_id";
      return false;
   }

   if(SYSTEM_ExtractJsonStringField(json, "side", command.side))
      command.has_side = true;
   if(SYSTEM_ExtractJsonDoubleField(json, "volume", command.volume))
      command.has_volume = true;
   if(SYSTEM_ExtractJsonDoubleField(json, "stop_loss", command.stop_loss))
      command.has_stop_loss = true;
   if(SYSTEM_ExtractJsonDoubleField(json, "take_profit", command.take_profit))
      command.has_take_profit = true;
   if(SYSTEM_ExtractJsonIntField(json, "ticket", command.ticket))
      command.has_ticket = true;
   if(SYSTEM_ExtractJsonStringField(json, "order_comment", command.order_comment))
      command.has_order_comment = true;

   return true;
}

bool SYSTEM_ValidateControlInstance(
   const SYSTEM_ControlCommand &command,
   const string expected_account_id,
   const string expected_symbol,
   const int expected_magic,
   string &error_message
)
{
   error_message = "";
   if(command.account_id != expected_account_id)
   {
      error_message = "control account_id does not match instance";
      return false;
   }
   if(command.symbol != expected_symbol)
   {
      error_message = "control symbol does not match instance";
      return false;
   }
   if(command.magic != expected_magic)
   {
      error_message = "control magic does not match instance";
      return false;
   }
   return true;
}

bool SYSTEM_ReadControlCommand(
   const string account_id,
   const string symbol,
   const int magic,
   SYSTEM_ControlCommand &command,
   string &error_message
)
{
   SYSTEM_ResetControlCommand(command);
   error_message = "";

   string path = SYSTEM_BuildControlFilePath(account_id, symbol, magic);
   if(!SYSTEM_IsControlReady(path))
   {
      error_message = "control file is not ready";
      return false;
   }

   string json = "";
   if(!SYSTEM_ReadTextFile(path, json))
   {
      error_message = "failed to read control file";
      return false;
   }

   if(!SYSTEM_ParseControlCommand(json, command, error_message))
      return false;

   if(!SYSTEM_ValidateControlInstance(command, account_id, symbol, magic, error_message))
      return false;

   return true;
}

bool SYSTEM_ControlPerformsAnalysis()
{
   return false;
}

#endif
