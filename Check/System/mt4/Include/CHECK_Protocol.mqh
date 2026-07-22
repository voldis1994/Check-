#ifndef __CHECK_PROTOCOL_MQH__
#define __CHECK_PROTOCOL_MQH__
#property strict

#define CHECK_PROTOCOL_VERSION "2.0.0"
#define CHECK_EA_VERSION "2.0.0"
#define CHECK_MSG_MARKET "market_snapshot"
#define CHECK_MSG_STATUS "status_snapshot"
#define CHECK_MSG_COMMAND "command"
#define CHECK_MSG_ACK "acknowledgement"
#define CHECK_SOURCE_MT4 "mt4"
#define CHECK_SOURCE_PYTHON "python"

#define CHECK_BRIDGE_REL "runtime\\bridge"
#define CHECK_DIR_MARKET "market"
#define CHECK_DIR_STATUS "status"
#define CHECK_DIR_COMMANDS "commands"
#define CHECK_DIR_ACKS "acknowledgements"
#define CHECK_DIR_ARCHIVE "archive"

#define CHECK_ACK_SUCCESS "SUCCESS"
#define CHECK_ACK_FAILED "FAILED"
#define CHECK_ACK_REJECTED "REJECTED"
#define CHECK_ACK_ALREADY "ALREADY_PROCESSED"

#define CHECK_ACTION_OPEN "OPEN"
#define CHECK_ACTION_MODIFY "MODIFY"
#define CHECK_ACTION_CLOSE "CLOSE"

#define CHECK_SIDE_BUY "BUY"
#define CHECK_SIDE_SELL "SELL"

#define CHECK_DEFAULT_SLIPPAGE 3
#define CHECK_MARKET_BARS_MAX 500
#define CHECK_EXPORT_INTERVAL_MS 500

#define CHECK_INVALID_HANDLE_VALUE -1
#define CHECK_INVALID_FILE_ATTRIBUTES -1
#define CHECK_FILE_ATTRIBUTE_DIRECTORY 16
#define CHECK_FILE_ATTRIBUTE_NORMAL 128
#define CHECK_GENERIC_WRITE 0x40000000
#define CHECK_GENERIC_READ 0x80000000
#define CHECK_CREATE_ALWAYS 2
#define CHECK_OPEN_EXISTING 3
#define CHECK_FILE_SHARE_READ 1
#define CHECK_MOVE_REPLACE_EXISTING 0x00000001
#define CHECK_ERROR_ALREADY_EXISTS 183
#define CHECK_FIND_DATA_SIZE 592
#define CHECK_FIND_NAME_OFFSET 44

#import "kernel32.dll"
   int CreateFileW(string lpFileName, uint dwDesiredAccess, uint dwShareMode, int lpSecurityAttributes, uint dwCreationDisposition, uint dwFlagsAndAttributes, int hTemplateFile);
   int WriteFile(int hFile, uchar &lpBuffer[], int nNumberOfBytesToWrite, int &lpNumberOfBytesWritten[], int lpOverlapped);
   int ReadFile(int hFile, uchar &lpBuffer[], int nNumberOfBytesToRead, int &lpNumberOfBytesRead[], int lpOverlapped);
   int FlushFileBuffers(int hFile);
   int CloseHandle(int hFile);
   int MoveFileExW(string lpExistingFileName, string lpNewFileName, uint dwFlags);
   int DeleteFileW(string lpFileName);
   int GetFileAttributesW(string lpFileName);
   int CreateDirectoryW(string lpPathName, int lpSecurityAttributes);
   int FindFirstFileW(string lpFileName, uchar &lpFindFileData[]);
   int FindNextFileW(int hFindFile, uchar &lpFindFileData[]);
   int FindClose(int hFindFile);
#import

string g_check_bridge_root = "";
string g_check_symbol = "";
int    g_check_magic = 0;
long   g_check_sequence = 0;
uint   g_check_last_export_ms = 0;
string g_check_processed_ids = "";

string CHECK_ProtocolVersion()
{
   return CHECK_PROTOCOL_VERSION;
}

string CHECK_JoinPath(const string left, const string right)
{
   if(StringLen(left) == 0)
      return right;
   if(StringLen(right) == 0)
      return left;

   string a = left;
   string b = right;
   int a_len = StringLen(a);
   int last = StringGetCharacter(a, a_len - 1);
   if(last == '\\' || last == '/')
      a = StringSubstr(a, 0, a_len - 1);
   int first = StringGetCharacter(b, 0);
   if(first == '\\' || first == '/')
      b = StringSubstr(b, 1);
   return a + "\\" + b;
}

string CHECK_NormalizeSeparators(const string path)
{
   string out = path;
   StringReplace(out, "/", "\\");
   return out;
}

string CHECK_BridgeRoot()
{
   return g_check_bridge_root;
}

string CHECK_BridgeDir(const string leaf)
{
   return CHECK_JoinPath(CHECK_JoinPath(g_check_bridge_root, CHECK_BRIDGE_REL), leaf);
}

string CHECK_MarketDir() { return CHECK_BridgeDir(CHECK_DIR_MARKET); }
string CHECK_StatusDir() { return CHECK_BridgeDir(CHECK_DIR_STATUS); }
string CHECK_CommandsDir() { return CHECK_BridgeDir(CHECK_DIR_COMMANDS); }
string CHECK_AcksDir() { return CHECK_BridgeDir(CHECK_DIR_ACKS); }
string CHECK_ArchiveDir() { return CHECK_BridgeDir(CHECK_DIR_ARCHIVE); }

string CHECK_ProcessedIdsPath()
{
   return CHECK_JoinPath(
      CHECK_ArchiveDir(),
      "processed_commands_" + g_check_symbol + "_" + IntegerToString(g_check_magic) + ".txt"
   );
}

string CHECK_SequencePath()
{
   return CHECK_JoinPath(
      CHECK_ArchiveDir(),
      "sequence_" + g_check_symbol + "_" + IntegerToString(g_check_magic) + ".txt"
   );
}

string CHECK_ParentDirectory(const string path)
{
   int separator = -1;
   for(int index = StringLen(path) - 1; index >= 0; index--)
   {
      int ch = StringGetCharacter(path, index);
      if(ch == '\\' || ch == '/')
      {
         separator = index;
         break;
      }
   }
   if(separator <= 0)
      return "";
   return StringSubstr(path, 0, separator);
}

bool CHECK_DirectoryExists(const string path)
{
   if(StringLen(path) == 0)
      return false;
   int attributes = GetFileAttributesW(path);
   if(attributes == CHECK_INVALID_FILE_ATTRIBUTES)
      return false;
   return (attributes & CHECK_FILE_ATTRIBUTE_DIRECTORY) != 0;
}

bool CHECK_FileExistsAbs(const string path)
{
   if(StringLen(path) == 0)
      return false;
   int attributes = GetFileAttributesW(path);
   return attributes != CHECK_INVALID_FILE_ATTRIBUTES
      && (attributes & CHECK_FILE_ATTRIBUTE_DIRECTORY) == 0;
}

bool CHECK_EnsureDirectory(const string path)
{
   if(StringLen(path) == 0)
      return false;
   if(CHECK_DirectoryExists(path))
      return true;

   string parent = CHECK_ParentDirectory(path);
   if(StringLen(parent) > 0 && !CHECK_EnsureDirectory(parent))
      return false;

   if(CreateDirectoryW(path, 0) != 0)
      return true;
   return GetLastError() == CHECK_ERROR_ALREADY_EXISTS || CHECK_DirectoryExists(path);
}

bool CHECK_EnsureBridgeDirectories()
{
   if(!CHECK_EnsureDirectory(CHECK_JoinPath(g_check_bridge_root, CHECK_BRIDGE_REL)))
      return false;
   if(!CHECK_EnsureDirectory(CHECK_MarketDir()))
      return false;
   if(!CHECK_EnsureDirectory(CHECK_StatusDir()))
      return false;
   if(!CHECK_EnsureDirectory(CHECK_CommandsDir()))
      return false;
   if(!CHECK_EnsureDirectory(CHECK_AcksDir()))
      return false;
   if(!CHECK_EnsureDirectory(CHECK_ArchiveDir()))
      return false;
   if(!CHECK_EnsureDirectory(CHECK_JoinPath(CHECK_ArchiveDir(), CHECK_DIR_COMMANDS)))
      return false;
   return true;
}

string CHECK_TmpPathFor(const string path)
{
   return path + ".tmp";
}

bool CHECK_AtomicWriteText(const string path, const string content)
{
   if(StringLen(path) == 0)
      return false;

   string parent_dir = CHECK_ParentDirectory(path);
   if(StringLen(parent_dir) > 0 && !CHECK_EnsureDirectory(parent_dir))
      return false;

   string tmp_path = CHECK_TmpPathFor(path);
   uchar buffer[];
   int bytes = StringToCharArray(content, buffer, 0, WHOLE_ARRAY, CP_UTF8);
   if(bytes <= 0)
      return false;

   int payload_bytes = bytes - 1;
   if(payload_bytes < 0)
      payload_bytes = 0;

   int handle = CreateFileW(
      tmp_path,
      CHECK_GENERIC_WRITE,
      0,
      0,
      CHECK_CREATE_ALWAYS,
      CHECK_FILE_ATTRIBUTE_NORMAL,
      0
   );
   if(handle == CHECK_INVALID_HANDLE_VALUE)
      return false;

   int written[];
   ArrayResize(written, 1);
   written[0] = 0;

   bool write_ok = WriteFile(handle, buffer, payload_bytes, written, 0) != 0;
   bool flush_ok = FlushFileBuffers(handle) != 0;
   bool close_ok = CloseHandle(handle) != 0;
   if(!write_ok || !flush_ok || !close_ok)
      return false;

   for(int attempt = 0; attempt < 8; attempt++)
   {
      if(MoveFileExW(tmp_path, path, CHECK_MOVE_REPLACE_EXISTING) != 0)
         return true;
      Sleep(25);
   }
   return false;
}

bool CHECK_ReadTextFile(const string path, string &content)
{
   content = "";
   if(!CHECK_FileExistsAbs(path))
      return true;

   int handle = CreateFileW(
      path,
      CHECK_GENERIC_READ,
      CHECK_FILE_SHARE_READ,
      0,
      CHECK_OPEN_EXISTING,
      CHECK_FILE_ATTRIBUTE_NORMAL,
      0
   );
   if(handle == CHECK_INVALID_HANDLE_VALUE)
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

bool CHECK_MoveFileAbs(const string from_path, const string to_path)
{
   string parent = CHECK_ParentDirectory(to_path);
   if(StringLen(parent) > 0 && !CHECK_EnsureDirectory(parent))
      return false;
   for(int attempt = 0; attempt < 8; attempt++)
   {
      if(MoveFileExW(from_path, to_path, CHECK_MOVE_REPLACE_EXISTING) != 0)
         return true;
      Sleep(25);
   }
   return false;
}

string CHECK_FindDataFileName(uchar &data[])
{
   string name = "";
   int offset = CHECK_FIND_NAME_OFFSET;
   int size = ArraySize(data);
   while(offset + 1 < size)
   {
      int lo = data[offset];
      int hi = data[offset + 1];
      int ch = lo + (hi << 8);
      if(ch == 0)
         break;
      name += ShortToString((short)ch);
      offset += 2;
   }
   return name;
}

int CHECK_ListJsonFiles(const string directory, string &names[])
{
   ArrayResize(names, 0);
   if(!CHECK_DirectoryExists(directory))
      return 0;

   string pattern = CHECK_JoinPath(directory, "*.json");
   uchar find_data[];
   ArrayResize(find_data, CHECK_FIND_DATA_SIZE);
   ArrayInitialize(find_data, 0);

   int handle = FindFirstFileW(pattern, find_data);
   if(handle == CHECK_INVALID_HANDLE_VALUE)
      return 0;

   do
   {
      string name = CHECK_FindDataFileName(find_data);
      if(StringLen(name) > 0 && name != "." && name != "..")
      {
         if(StringFind(name, ".tmp", 0) < 0 && StringFind(name, ".ack.json", 0) < 0)
         {
            int n = ArraySize(names);
            ArrayResize(names, n + 1);
            names[n] = name;
         }
      }
      ArrayInitialize(find_data, 0);
   }
   while(FindNextFileW(handle, find_data) != 0);

   FindClose(handle);

   // Ascending lexicographic order => sequence prefixes sort correctly for zero-padded / numeric prefixes.
   int total = ArraySize(names);
   for(int i = 0; i < total; i++)
   {
      for(int j = i + 1; j < total; j++)
      {
         if(names[j] < names[i])
         {
            string tmp = names[i];
            names[i] = names[j];
            names[j] = tmp;
         }
      }
   }
   return total;
}

datetime CHECK_ToUtcTime(const datetime server_time)
{
   return server_time + (TimeGMT() - TimeCurrent());
}

string CHECK_FormatTimeUtc(const datetime time_value)
{
   MqlDateTime parts;
   TimeToStruct(CHECK_ToUtcTime(time_value), parts);
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

string CHECK_NowUtcIso()
{
   return CHECK_FormatTimeUtc(TimeCurrent());
}

string CHECK_NewMessageId()
{
   // Deterministic-enough unique id without a crypto RNG (MQL4 constraint).
   uint a = (uint)TimeGMT();
   uint b = GetTickCount();
   uint c = (uint)g_check_sequence;
   uint d = (uint)(a ^ (b * 2654435761));
   return StringFormat(
      "%08x-%04x-4%03x-8%03x-%08x%04x",
      a,
      (b >> 16) & 0xFFFF,
      c & 0x0FFF,
      (d >> 4) & 0x0FFF,
      d,
      b & 0xFFFF
   );
}

long CHECK_NextSequence()
{
   g_check_sequence++;
   CHECK_AtomicWriteText(CHECK_SequencePath(), IntegerToString((int)g_check_sequence) + "\n");
   return g_check_sequence;
}

void CHECK_LoadSequence()
{
   string content = "";
   if(!CHECK_ReadTextFile(CHECK_SequencePath(), content))
   {
      g_check_sequence = 0;
      return;
   }
   StringTrimLeft(content);
   StringTrimRight(content);
   if(StringLen(content) == 0)
      g_check_sequence = 0;
   else
      g_check_sequence = StringToInteger(content);
}

void CHECK_LoadProcessedIds()
{
   string content = "";
   CHECK_ReadTextFile(CHECK_ProcessedIdsPath(), content);
   g_check_processed_ids = "\n" + content;
   if(StringFind(g_check_processed_ids, "\n", StringLen(g_check_processed_ids) - 1) < 0)
      g_check_processed_ids = g_check_processed_ids + "\n";
}

bool CHECK_IsCommandIdProcessed(const string command_id)
{
   if(StringLen(command_id) == 0)
      return false;
   string needle = "\n" + command_id + "\n";
   return StringFind(g_check_processed_ids, needle, 0) >= 0;
}

void CHECK_MarkCommandIdProcessed(const string command_id)
{
   if(StringLen(command_id) == 0)
      return;
   if(CHECK_IsCommandIdProcessed(command_id))
      return;
   g_check_processed_ids = g_check_processed_ids + command_id + "\n";
   string existing = "";
   CHECK_ReadTextFile(CHECK_ProcessedIdsPath(), existing);
   if(StringLen(existing) > 0 && StringGetCharacter(existing, StringLen(existing) - 1) != '\n')
      existing = existing + "\n";
   CHECK_AtomicWriteText(CHECK_ProcessedIdsPath(), existing + command_id + "\n");
}

double CHECK_PipSize(const string symbol)
{
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   double point = MarketInfo(symbol, MODE_POINT);
   if(point <= 0.0)
      point = MathPow(10.0, -MathMax(digits, 1));
   if(digits == 3 || digits == 5)
      return point * 10.0;
   return point;
}

double CHECK_PriceTolerance(const string symbol)
{
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits <= 0)
      digits = 5;
   double point = MarketInfo(symbol, MODE_POINT);
   if(point <= 0.0)
      point = MathPow(10.0, -digits);
   return MathMax(point, MathPow(10.0, -digits));
}

double CHECK_NormalizePrice(const string symbol, const double price)
{
   if(price <= 0.0)
      return 0.0;
   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   if(digits < 0)
      digits = 5;
   return NormalizeDouble(price, digits);
}

double CHECK_NormalizeLot(const string symbol, const double lots)
{
   double step = MarketInfo(symbol, MODE_LOTSTEP);
   if(step <= 0.0)
      step = 0.01;
   double normalized = MathFloor(lots / step + 1e-12) * step;
   int lot_digits = 2;
   if(step < 0.01)
      lot_digits = 3;
   return NormalizeDouble(normalized, lot_digits);
}

bool CHECK_IsMarketOpen(const string symbol)
{
   double bid = MarketInfo(symbol, MODE_BID);
   double ask = MarketInfo(symbol, MODE_ASK);
   if(bid <= 0.0 || ask <= 0.0)
      return false;
   return MarketInfo(symbol, MODE_TRADEALLOWED) != 0.0;
}

#endif
