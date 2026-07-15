#ifndef __SYSTEM_IO_MQH__
#define __SYSTEM_IO_MQH__

#property strict

#include <SYSTEM_Paths.mqh>

#define SYSTEM_GENERIC_WRITE 0x40000000
#define SYSTEM_CREATE_ALWAYS 2
#define SYSTEM_FILE_ATTRIBUTE_NORMAL 128
#define SYSTEM_INVALID_HANDLE_VALUE -1
#define SYSTEM_MOVE_REPLACE_EXISTING 0x00000001
#define SYSTEM_COMMON_BRIDGE_PREFIX "CheckSystem"

#import "kernel32.dll"
   int CreateFileW(
      string lpFileName,
      uint dwDesiredAccess,
      uint dwShareMode,
      int lpSecurityAttributes,
      uint dwCreationDisposition,
      uint dwFlagsAndAttributes,
      int hTemplateFile
   );
   int WriteFile(
      int hFile,
      uchar &lpBuffer[],
      int nNumberOfBytesToWrite,
      int &lpNumberOfBytesWritten[],
      int lpOverlapped
   );
   int FlushFileBuffers(int hFile);
   int CloseHandle(int hFile);
   int MoveFileExW(string lpExistingFileName, string lpNewFileName, uint dwFlags);
   int ReadFile(
      int hFile,
      uchar &lpBuffer[],
      int nNumberOfBytesToRead,
      int &lpNumberOfBytesRead[],
      int lpOverlapped
   );
#import

string SYSTEM_TmpPathFor(const string path)
{
   return path + ".tmp";
}

string SYSTEM_ParentDirectory(const string path)
{
   int separator = -1;
   for(int index = StringLen(path) - 1; index >= 0; index--)
   {
      if(StringGetCharacter(path, index) == '\\')
      {
         separator = index;
         break;
      }
   }

   if(separator <= 0)
      return "";

   return StringSubstr(path, 0, separator);
}

string SYSTEM_NormalizePathSlashes(const string path)
{
   string out = path;
   StringReplace(out, "/", "\\");
   return out;
}

string SYSTEM_ToCommonRelative(const string absolute_path)
{
   string abs_norm = SYSTEM_NormalizePathSlashes(absolute_path);
   string root_norm = SYSTEM_NormalizePathSlashes(SYSTEM_GetRootPath());
   int root_len = StringLen(root_norm);
   if(root_len > 0 && StringFind(abs_norm, root_norm) == 0)
   {
      string suffix = StringSubstr(abs_norm, root_len);
      if(StringLen(suffix) > 0 && StringGetCharacter(suffix, 0) == '\\')
         suffix = StringSubstr(suffix, 1);
      if(StringLen(suffix) == 0)
         return SYSTEM_COMMON_BRIDGE_PREFIX;
      return SYSTEM_COMMON_BRIDGE_PREFIX + "\\" + suffix;
   }
   return SYSTEM_COMMON_BRIDGE_PREFIX + "\\unmapped\\" + abs_norm;
}

bool SYSTEM_EnsureCommonDirectoryTree(const string relative_dir)
{
   if(StringLen(relative_dir) == 0)
      return true;

   string normalized = SYSTEM_NormalizePathSlashes(relative_dir);
   string accumulated = "";
   int start = 0;
   int len = StringLen(normalized);
   for(int index = 0; index <= len; index++)
   {
      bool at_end = (index == len);
      bool is_sep = (!at_end && StringGetCharacter(normalized, index) == '\\');
      if(!at_end && !is_sep)
         continue;

      string part = StringSubstr(normalized, start, index - start);
      start = index + 1;
      if(StringLen(part) == 0)
         continue;
      if(StringLen(accumulated) == 0)
         accumulated = part;
      else
         accumulated = accumulated + "\\" + part;
      if(!FolderCreate(accumulated, FILE_COMMON))
      {
         // Folder may already exist — continue; FileOpen will fail later if really missing.
      }
   }
   return true;
}

bool SYSTEM_AtomicWriteTextDll(const string path, const string content)
{
   string parent_dir = SYSTEM_ParentDirectory(path);
   if(StringLen(parent_dir) > 0 && !SYSTEM_EnsureDirectory(parent_dir))
      return false;

   string tmp_path = SYSTEM_TmpPathFor(path);
   uchar buffer[];
   int bytes = StringToCharArray(content, buffer, 0, WHOLE_ARRAY, CP_UTF8);
   if(bytes <= 0)
      return false;

   int payload_bytes = bytes - 1;
   if(payload_bytes < 0)
      payload_bytes = 0;

   int handle = CreateFileW(
      tmp_path,
      SYSTEM_GENERIC_WRITE,
      0,
      0,
      SYSTEM_CREATE_ALWAYS,
      SYSTEM_FILE_ATTRIBUTE_NORMAL,
      0
   );
   if(handle == SYSTEM_INVALID_HANDLE_VALUE)
      return false;

   int written[];
   ArrayResize(written, 1);
   written[0] = 0;

   bool write_ok = WriteFile(handle, buffer, payload_bytes, written, 0) != 0;
   bool flush_ok = FlushFileBuffers(handle) != 0;
   bool close_ok = CloseHandle(handle) != 0;

   if(!write_ok || !flush_ok || !close_ok)
      return false;

   if(!MoveFileExW(tmp_path, path, SYSTEM_MOVE_REPLACE_EXISTING))
      return false;

   return true;
}

bool SYSTEM_AtomicWriteTextCommon(const string absolute_path, const string content)
{
   string relative = SYSTEM_ToCommonRelative(absolute_path);
   string parent = SYSTEM_ParentDirectory(relative);
   if(!SYSTEM_EnsureCommonDirectoryTree(parent))
      return false;

   string tmp_relative = relative + ".tmp";
   FileDelete(tmp_relative, FILE_COMMON);

   int handle = FileOpen(tmp_relative, FILE_TXT | FILE_WRITE | FILE_ANSI | FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      Print("SYSTEM common FileOpen failed for ", tmp_relative, " err=", GetLastError());
      return false;
   }

   ResetLastError();
   FileWriteString(handle, content);
   FileClose(handle);

   FileDelete(relative, FILE_COMMON);
   if(!FileMove(tmp_relative, FILE_COMMON, relative, FILE_COMMON))
   {
      // Fallback: rewrite destination directly.
      int direct = FileOpen(relative, FILE_TXT | FILE_WRITE | FILE_ANSI | FILE_COMMON);
      if(direct == INVALID_HANDLE)
         return false;
      FileWriteString(direct, content);
      FileClose(direct);
      FileDelete(tmp_relative, FILE_COMMON);
   }
   return true;
}

bool SYSTEM_AtomicWriteText(const string path, const string content)
{
   if(StringLen(path) == 0)
      return false;

   if(SYSTEM_AtomicWriteTextDll(path, content))
      return true;

   int dll_error = 0;
   Print("SYSTEM DLL write failed for ", path, " — using Common\\Files fallback (enable Allow DLL imports for direct C:\\Check\\System writes)");
   return SYSTEM_AtomicWriteTextCommon(path, content);
}

#endif
