#ifndef __CHECK_JSON_MQH__
#define __CHECK_JSON_MQH__
#property strict

string CHECK_EscapeJsonString(const string value)
{
   string out = value;
   StringReplace(out, "\\", "\\\\");
   StringReplace(out, "\"", "\\\"");
   StringReplace(out, "\n", "\\n");
   StringReplace(out, "\r", "\\r");
   StringReplace(out, "\t", "\\t");
   return out;
}

string CHECK_FormatJsonNumber(const double value, const int digits)
{
   return DoubleToStr(value, digits);
}

string CHECK_FormatJsonBoolean(const bool value)
{
   return value ? "true" : "false";
}

bool CHECK_ExtractJsonStringField(const string json, const string field_name, string &out_value)
{
   string needle = "\"" + field_name + "\":";
   int position = StringFind(json, needle, 0);
   if(position < 0)
      return false;

   position += StringLen(needle);
   int len = StringLen(json);
   while(position < len)
   {
      int ch = StringGetCharacter(json, position);
      if(ch != ' ' && ch != '\t' && ch != '\n' && ch != '\r')
         break;
      position++;
   }

   if(position >= len || StringGetCharacter(json, position) != '"')
      return false;

   position++;
   string value = "";
   bool escaped = false;
   while(position < len)
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

bool CHECK_ExtractJsonToken(const string json, const string field_name, string &out_token)
{
   string needle = "\"" + field_name + "\":";
   int position = StringFind(json, needle, 0);
   if(position < 0)
      return false;

   position += StringLen(needle);
   int len = StringLen(json);
   while(position < len)
   {
      int ch = StringGetCharacter(json, position);
      if(ch != ' ' && ch != '\t' && ch != '\n' && ch != '\r')
         break;
      position++;
   }

   int end = position;
   while(end < len)
   {
      int character = StringGetCharacter(json, end);
      if(character == ',' || character == '}' || character == ']' || character == '\n' || character == '\r')
         break;
      end++;
   }

   out_token = StringSubstr(json, position, end - position);
   StringTrimLeft(out_token);
   StringTrimRight(out_token);
   return StringLen(out_token) > 0;
}

bool CHECK_ExtractJsonIntField(const string json, const string field_name, int &out_value)
{
   string token = "";
   if(!CHECK_ExtractJsonToken(json, field_name, token))
      return false;
   out_value = (int)StringToInteger(token);
   return true;
}

bool CHECK_ExtractJsonLongField(const string json, const string field_name, long &out_value)
{
   string token = "";
   if(!CHECK_ExtractJsonToken(json, field_name, token))
      return false;
   out_value = StringToInteger(token);
   return true;
}

bool CHECK_ExtractJsonDoubleField(const string json, const string field_name, double &out_value)
{
   string token = "";
   if(!CHECK_ExtractJsonToken(json, field_name, token))
      return false;
   out_value = StringToDouble(token);
   return true;
}

bool CHECK_ExtractJsonBoolField(const string json, const string field_name, bool &out_value)
{
   string token = "";
   if(!CHECK_ExtractJsonToken(json, field_name, token))
      return false;
   if(token == "true" || token == "1")
   {
      out_value = true;
      return true;
   }
   if(token == "false" || token == "0")
   {
      out_value = false;
      return true;
   }
   return false;
}

string CHECK_JsonKvString(const string key, const string value, const bool trailing_comma)
{
   string line = "  \"" + key + "\": \"" + CHECK_EscapeJsonString(value) + "\"";
   if(trailing_comma)
      line = line + ",";
   return line + "\n";
}

string CHECK_JsonKvInt(const string key, const int value, const bool trailing_comma)
{
   string line = "  \"" + key + "\": " + IntegerToString(value);
   if(trailing_comma)
      line = line + ",";
   return line + "\n";
}

string CHECK_JsonKvLong(const string key, const long value, const bool trailing_comma)
{
   string line = "  \"" + key + "\": " + IntegerToString((int)value);
   if(trailing_comma)
      line = line + ",";
   return line + "\n";
}

string CHECK_JsonKvNumber(const string key, const double value, const int digits, const bool trailing_comma)
{
   string line = "  \"" + key + "\": " + CHECK_FormatJsonNumber(value, digits);
   if(trailing_comma)
      line = line + ",";
   return line + "\n";
}

string CHECK_JsonKvBool(const string key, const bool value, const bool trailing_comma)
{
   string line = "  \"" + key + "\": " + CHECK_FormatJsonBoolean(value);
   if(trailing_comma)
      line = line + ",";
   return line + "\n";
}

#endif
