#ifndef __SYSTEM_IO_MQH__
#define __SYSTEM_IO_MQH__

#property strict

#include <SYSTEM_Paths.mqh>

#define SYSTEM_GENERIC_WRITE 0x40000000
#define SYSTEM_CREATE_ALWAYS 2
#define SYSTEM_FILE_ATTRIBUTE_NORMAL 128
#define SYSTEM_INVALID_HANDLE_VALUE -1
#define SYSTEM_MOVE_REPLACE_EXISTING 0x00000001

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

bool SYSTEM_AtomicWriteText(const string path, const string content)
{
   if(StringLen(path) == 0)
      return false;

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

#endif
