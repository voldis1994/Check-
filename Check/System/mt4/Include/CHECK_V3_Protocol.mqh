// CHECK SYSTEM v3 MT4 protocol helpers.
// The EA is a transport bridge only: it exports broker data and applies commands.
#ifndef CHECK_V3_PROTOCOL_MQH
#define CHECK_V3_PROTOCOL_MQH

#define CHECK_V3_PROTOCOL_VERSION "3.0.0"
#define CHECK_V3_MESSAGE_MARKET "MARKET"
#define CHECK_V3_MESSAGE_STATUS "STATUS"
#define CHECK_V3_MESSAGE_COMMAND "COMMAND"
#define CHECK_V3_MESSAGE_ACK "ACK"

#define CHECK_V3_MOVEFILE_REPLACE_EXISTING 1
#define CHECK_V3_MOVEFILE_COPY_ALLOWED 2
#define CHECK_V3_MOVEFILE_WRITE_THROUGH 8
#define CHECK_V3_FILE_ATTRIBUTE_DIRECTORY 16
#define CHECK_V3_INVALID_FILE_ATTRIBUTES -1

#import "kernel32.dll"
int  CreateDirectoryW(string lpPathName, int lpSecurityAttributes);
int  GetFileAttributesW(string lpFileName);
bool MoveFileExW(string lpExistingFileName, string lpNewFileName, int dwFlags);
bool DeleteFileW(string lpFileName);
#import

string CheckV3NormalizePath(string path)
{
   string p = path;
   StringReplace(p, "/", "\\");
   while(StringLen(p) > 1 && StringSubstr(p, StringLen(p) - 1, 1) == "\\")
      p = StringSubstr(p, 0, StringLen(p) - 1);
   return p;
}

string CheckV3PathJoin(string left, string right)
{
   string l = CheckV3NormalizePath(left);
   string r = CheckV3NormalizePath(right);
   if(StringLen(l) == 0)
      return r;
   if(StringLen(r) == 0)
      return l;
   if(StringSubstr(l, StringLen(l) - 1, 1) == "\\")
      return l + r;
   return l + "\\" + r;
}

bool CheckV3PathExists(string path)
{
   return GetFileAttributesW(CheckV3NormalizePath(path)) != CHECK_V3_INVALID_FILE_ATTRIBUTES;
}

bool CheckV3DirectoryExists(string path)
{
   int attrs = GetFileAttributesW(CheckV3NormalizePath(path));
   return attrs != CHECK_V3_INVALID_FILE_ATTRIBUTES && (attrs & CHECK_V3_FILE_ATTRIBUTE_DIRECTORY) != 0;
}

bool CheckV3EnsureDir(string path)
{
   string p = CheckV3NormalizePath(path);
   if(CheckV3DirectoryExists(p))
      return true;

   string parts[];
   int count = StringSplit(p, StringGetCharacter("\\", 0), parts);
   if(count <= 0)
      return false;

   string partial = "";
   for(int i = 0; i < count; i++)
   {
      if(parts[i] == "")
         continue;

      if(partial == "")
         partial = parts[i];
      else
         partial = partial + "\\" + parts[i];

      if(StringLen(partial) == 2 && StringSubstr(partial, 1, 1) == ":")
         continue;

      if(!CheckV3DirectoryExists(partial))
      {
         CreateDirectoryW(partial, 0);
         if(!CheckV3DirectoryExists(partial))
         {
            Print("CHECK v3: failed to create directory: ", partial, " error=", GetLastError());
            return false;
         }
      }
   }

   return CheckV3DirectoryExists(p);
}

string CheckV3UtcIso()
{
   string s = TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS);
   StringReplace(s, ".", "-");
   StringReplace(s, " ", "T");
   return s + "Z";
}

string CheckV3TimeIso(datetime value)
{
   // Bar open times from iTime() are broker/server time. Convert to GMT so the
   // trailing Z is honest (otherwise live freshness / session math drifts).
   datetime gmt = value - (TimeCurrent() - TimeGMT());
   string s = TimeToString(gmt, TIME_DATE | TIME_SECONDS);
   StringReplace(s, ".", "-");
   StringReplace(s, " ", "T");
   return s + "Z";
}

string CheckV3MessageId(string messageType, int sequence)
{
   return messageType + "-" + IntegerToString(AccountNumber()) + "-" + Symbol() + "-" +
          IntegerToString(sequence) + "-" + IntegerToString(GetTickCount());
}

string CheckV3JsonEscape(string value)
{
   string out = "";
   for(int i = 0; i < StringLen(value); i++)
   {
      string c = StringSubstr(value, i, 1);
      if(c == "\\")
         out += "\\\\";
      else if(c == "\"")
         out += "\\\"";
      else if(c == "\r")
         out += "\\r";
      else if(c == "\n")
         out += "\\n";
      else if(c == "\t")
         out += "\\t";
      else
         out += c;
   }
   return out;
}

string CheckV3JsonString(string value)
{
   return "\"" + CheckV3JsonEscape(value) + "\"";
}

string CheckV3UpperAscii(string value)
{
   string out = "";
   for(int i = 0; i < StringLen(value); i++)
   {
      string c = StringSubstr(value, i, 1);
      if(c == "a") c = "A";
      else if(c == "b") c = "B";
      else if(c == "c") c = "C";
      else if(c == "d") c = "D";
      else if(c == "e") c = "E";
      else if(c == "f") c = "F";
      else if(c == "g") c = "G";
      else if(c == "h") c = "H";
      else if(c == "i") c = "I";
      else if(c == "j") c = "J";
      else if(c == "k") c = "K";
      else if(c == "l") c = "L";
      else if(c == "m") c = "M";
      else if(c == "n") c = "N";
      else if(c == "o") c = "O";
      else if(c == "p") c = "P";
      else if(c == "q") c = "Q";
      else if(c == "r") c = "R";
      else if(c == "s") c = "S";
      else if(c == "t") c = "T";
      else if(c == "u") c = "U";
      else if(c == "v") c = "V";
      else if(c == "w") c = "W";
      else if(c == "x") c = "X";
      else if(c == "y") c = "Y";
      else if(c == "z") c = "Z";
      out += c;
   }
   return out;
}

string CheckV3JsonBool(bool value)
{
   return value ? "true" : "false";
}

string CheckV3JsonNumber(double value, int digits = 8)
{
   return DoubleToString(value, digits);
}

string CheckV3Mql4FilesRoot()
{
   return CheckV3NormalizePath(CheckV3PathJoin(TerminalInfoString(TERMINAL_DATA_PATH), "MQL4\\Files"));
}

string CheckV3ToAbsoluteUnderFiles(string path)
{
   string p = CheckV3NormalizePath(path);
   if(StringFind(p, ":") >= 0)
      return p;
   return CheckV3PathJoin(CheckV3Mql4FilesRoot(), p);
}

string CheckV3ToRelativeFilesPath(string path)
{
   string abs = CheckV3ToAbsoluteUnderFiles(path);
   string root = CheckV3Mql4FilesRoot() + "\\";
   string absU = CheckV3UpperAscii(abs);
   string rootU = CheckV3UpperAscii(root);
   if(StringFind(absU, rootU) == 0)
      return StringSubstr(abs, StringLen(root));
   return abs;
}

bool CheckV3WriteTextDirect(string relTarget, string content)
{
   ResetLastError();
   int handle = FileOpen(relTarget, FILE_WRITE | FILE_BIN | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return false;
   FileWriteString(handle, content);
   FileFlush(handle);
   FileClose(handle);
   return true;
}

bool CheckV3MoveReplaceWithRetry(string tempAbs, string targetAbs, string relTemp, string relTarget, string content)
{
   // Python may hold latest.json open briefly → ERROR_SHARING_VIOLATION (32).
   int flags = CHECK_V3_MOVEFILE_REPLACE_EXISTING |
               CHECK_V3_MOVEFILE_COPY_ALLOWED;
   for(int attempt = 0; attempt < 8; attempt++)
   {
      ResetLastError();
      if(MoveFileExW(tempAbs, targetAbs, flags))
         return true;
      int err = GetLastError();
      // Delete target then retry move (helps when replace is denied).
      DeleteFileW(targetAbs);
      ResetLastError();
      if(MoveFileExW(tempAbs, targetAbs, flags))
         return true;
      Sleep(25 + attempt * 15);
      if(attempt >= 6)
         Print("CHECK v3: atomic move retry ", attempt, " from ", tempAbs, " to ", targetAbs, " error=", err);
   }

   // Last resort: direct overwrite so EXPORT still updates (better than stale bridge).
   FileDelete(relTemp);
   if(CheckV3WriteTextDirect(relTarget, content))
   {
      Print("CHECK v3: atomic move failed — wrote direct to ", relTarget);
      return true;
   }
   Print("CHECK v3: atomic move failed from ", tempAbs, " to ", targetAbs, " error=", GetLastError());
   return false;
}

bool CheckV3WriteTextAtomic(string targetPath, string content)
{
   // MQL4 FileOpen only accepts paths relative to TerminalDataPath\MQL4\Files.
   // Absolute paths silently fail — which left stale bridge JSON on disk.
   string targetAbs = CheckV3ToAbsoluteUnderFiles(targetPath);
   string relTarget = CheckV3ToRelativeFilesPath(targetAbs);
   string relTemp = relTarget + ".tmp." + IntegerToString(GetTickCount()) + "." + IntegerToString(MathRand());
   string tempAbs = CheckV3PathJoin(CheckV3Mql4FilesRoot(), relTemp);

   // Ensure parent folder exists under Files\
   int slash = StringLen(relTarget) - 1;
   while(slash >= 0 && StringSubstr(relTarget, slash, 1) != "\\")
      slash--;
   if(slash > 0)
      CheckV3EnsureDir(CheckV3PathJoin(CheckV3Mql4FilesRoot(), StringSubstr(relTarget, 0, slash)));

   ResetLastError();
   int handle = FileOpen(relTemp, FILE_WRITE | FILE_BIN | FILE_ANSI);
   if(handle == INVALID_HANDLE)
   {
      Print("CHECK v3: failed to open temp file: ", relTemp, " error=", GetLastError());
      return false;
   }

   FileWriteString(handle, content);
   FileFlush(handle);
   FileClose(handle);

   if(!CheckV3MoveReplaceWithRetry(tempAbs, targetAbs, relTemp, relTarget, content))
   {
      FileDelete(relTemp);
      return false;
   }
   return true;
}

string CheckV3ReadText(string path)
{
   string rel = CheckV3ToRelativeFilesPath(path);
   ResetLastError();
   int handle = FileOpen(rel, FILE_READ | FILE_BIN | FILE_ANSI);
   if(handle == INVALID_HANDLE)
      return "";

   int size = (int)FileSize(handle);
   string content = "";
   if(size > 0)
      content = FileReadString(handle, size);
   FileClose(handle);
   return content;
}

int CheckV3FindKeyStart(string json, string key)
{
   return StringFind(json, "\"" + key + "\"");
}

int CheckV3FindValueStart(string json, int keyStart)
{
   if(keyStart < 0)
      return -1;
   int colon = StringFind(json, ":", keyStart);
   if(colon < 0)
      return -1;
   int pos = colon + 1;
   while(pos < StringLen(json))
   {
      string c = StringSubstr(json, pos, 1);
      if(c != " " && c != "\r" && c != "\n" && c != "\t")
         break;
      pos++;
   }
   return pos;
}

string CheckV3JsonGetString(string json, string key, string defaultValue = "")
{
   int pos = CheckV3FindValueStart(json, CheckV3FindKeyStart(json, key));
   if(pos < 0 || StringSubstr(json, pos, 1) != "\"")
      return defaultValue;

   pos++;
   string out = "";
   while(pos < StringLen(json))
   {
      string c = StringSubstr(json, pos, 1);
      if(c == "\\")
      {
         pos++;
         if(pos >= StringLen(json))
            break;
         string e = StringSubstr(json, pos, 1);
         if(e == "n")
            out += "\n";
         else if(e == "r")
            out += "\r";
         else if(e == "t")
            out += "\t";
         else
            out += e;
      }
      else if(c == "\"")
         return out;
      else
         out += c;
      pos++;
   }
   return defaultValue;
}

double CheckV3JsonGetNumber(string json, string key, double defaultValue = 0.0)
{
   int pos = CheckV3FindValueStart(json, CheckV3FindKeyStart(json, key));
   if(pos < 0)
      return defaultValue;

   int end = pos;
   while(end < StringLen(json))
   {
      string c = StringSubstr(json, end, 1);
      if((c >= "0" && c <= "9") || c == "." || c == "-" || c == "+")
         end++;
      else
         break;
   }
   if(end == pos)
      return defaultValue;
   return StrToDouble(StringSubstr(json, pos, end - pos));
}

bool CheckV3JsonGetBool(string json, string key, bool defaultValue = false)
{
   int pos = CheckV3FindValueStart(json, CheckV3FindKeyStart(json, key));
   if(pos < 0)
      return defaultValue;
   string token = StringSubstr(json, pos, 5);
   if(StringSubstr(token, 0, 4) == "true")
      return true;
   if(token == "false")
      return false;
   return defaultValue;
}

#endif
