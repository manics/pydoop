# BEGIN_COPYRIGHT
# END_COPYRIGHT

"""
This module provides facilities to connect to an HDFS and manipulate
its files and directories.
"""

import os, glob


DEFAULT_HADOOP_HOME = "/opt/hadoop"  # should only be useful for local use
HADOOP_HOME = os.getenv("HADOOP_HOME", DEFAULT_HADOOP_HOME)
HADOOP_CONF_DIR = os.getenv("HADOOP_CONF_DIR",
                            os.path.join(HADOOP_HOME, "conf"))

jars = glob.glob(os.path.join(HADOOP_HOME, "lib/*.jar"))
jars.extend(glob.glob(os.path.join(HADOOP_HOME, "hadoop*.jar")))
jars.append(HADOOP_CONF_DIR)

CLASSPATH = os.environ.setdefault("CLASSPATH", "")
CLASSPATH = "%s:%s" % (":".join(jars), CLASSPATH)
os.environ["CLASSPATH"] = CLASSPATH


from _hdfs import hdfs_fs


class hdfs_file(object):
  """
  Instances of this class represent HDFS file objects.

  Objects from this class should not be instantiated directly. To get an HDFS
  file object, call :meth:`hdfs.open_file`\ .
  """
  
  DEFAULT_CHUNK_SIZE = 16384
  ENDL = os.linesep

  def __init__(self, raw_hdfs_file, chunk_size=DEFAULT_CHUNK_SIZE):
    if not chunk_size > 0:
      raise ValueError("chunk size must be positive")
    self.f = raw_hdfs_file
    self.chunk_size = chunk_size
    self.__reset()

  def __reset(self):
    self.buffer_list = []
    self.chunk = ""
    self.EOF = False
    self.p = 0

  def __read_chunk(self):
    self.chunk = self.f.read(self.chunk_size)
    self.p = 0
    if not self.chunk:
      self.EOF = True

  def __read_chunks_until_nl(self):
    if self.EOF:
      eol = self.chunk.find(self.ENDL, self.p)
      return eol if eol > -1 else len(self.chunk)
    if not self.chunk:
      self.__read_chunk()
    eol = self.chunk.find(self.ENDL, self.p)
    i = 0
    while eol < 0 and not self.EOF:
      i += 1
      if i == 20: break
      if self.p < len(self.chunk):
        self.buffer_list.append(self.chunk[self.p:])
      self.__read_chunk()
      eol = self.chunk.find(self.ENDL, self.p)
    return eol if eol > -1 else len(self.chunk)

  def readline(self):
    """
    Read and return a line of text.

    :rtype: string
    :return: the next line of text in the file, including the newline character
    """
    eol = self.__read_chunks_until_nl()
    line = "".join(self.buffer_list) + self.chunk[self.p:eol+1]
    self.buffer_list = []
    self.p = eol+1
    return line
     
  def available(self):
    """
    Number of bytes that can be read from this input stream without blocking.

    :rtype: int
    :return: available bytes
    """
    return self.f.available()
  
  def close(self):
    """
    Close the file.
    """
    return self.f.close()
  
  def pread(self, position, length):
    """
    Read ``length`` bytes of data from the file, starting from ``position``\ .

    :type position: int
    :param position: position from which to read
    :type length: int
    :param length: the number of bytes to read
    :rtype: string
    :return: the chunk of data read from the file
    """
    return self.f.pread(position, length)
  
  def pread_chunk(self, position, chunk):
    """
    Works like :meth:`pread`\ , but data is stored in the writable
    buffer ``chunk`` rather than returned. Reads at most a number of
    bytes equal to the size of ``chunk``\ .

    :type position: int
    :param position: position from which to read
    :type chunk: writable string buffer
    :param chunk: a c-like string buffer, such as the one returned by the
      ``create_string_buffer`` function in the :mod:`ctypes` module
    :rtype: int
    :return: the number of bytes read
    """    
    return self.f.pread_chunk(position, chunk)
  
  def read(self, length):
    """
    Read ``length`` bytes from the file.

    :type length: int
    :param length: the number of bytes to read
    :rtype: string
    :return: the chunk of data read from the file
    """
    return self.f.read(length)
 
  def read_chunk(self, chunk):
    """
    Works like :meth:`read`\ , but data is stored in the writable
    buffer ``chunk`` rather than returned. Reads at most a number of
    bytes equal to the size of ``chunk``\ .

    :type chunk: writable string buffer
    :param chunk: a c-like string buffer, such as the one returned by the
      ``create_string_buffer`` function in the :mod:`ctypes` module
    :rtype: int
    :return: the number of bytes read
    """    
    return self.f.read_chunk(chunk)
  
  def seek(self, position):
    """
    Seek to ``position`` in file.

    :type position: int
    :param position: offset into the file to seek into
    """
    self.__reset()
    return self.f.seek(position)
  
  def tell(self):
    """
    Get the current byte offset in the file.

    :rtype: int
    :return: current offset in bytes
    """
    return self.f.tell()
  
  def write(self, data):
    """
    Write ``data`` to the file.

    :type data: string
    :param data: the data to be written to the file
    :rtype: int
    :return: the number of bytes written
    """
    return self.f.write(data)
  
  def write_chunk(self, chunk):
    """
    Write data from buffer ``chunk`` to the file.

    :type chunk: writable string buffer
    :param chunk: a c-like string buffer, such as the one returned by the
      ``create_string_buffer`` function in the :mod:`ctypes` module
    :rtype: int
    :return: the number of bytes written
    """
    return self.f.write_chunk(chunk)


class hdfs(hdfs_fs):
  """
  Represents a handle to an HDFS instance.

  :type host: string
  :param host: hostname or IP address of the HDFS NameNode. Set to
    an empty string (and ``port`` to 0) to connect to the local file
    system; Set to "default" (and ``port`` to 0) to connect to the
    "configured" file system.  
  :type port: int
  :param port: the port on which the NameNode is listening
  """
  def __init__(self, host, port):
    super(hdfs, self).__init__(host, port)

  def open_file(self, path,
                flags=os.O_RDONLY,
                buff_size=0,
                replication=0,
                blocksize=0,
                readline_chunk_size=hdfs_file.DEFAULT_CHUNK_SIZE):
    """
    Open an HDFS file.

    Pass 0 as buff_size, replication or blocksize if you want to use
    the default values, i.e., the ones set in the Hadoop configuration
    files.

    :type path: string
    :param path: the full path to the file
    :type flags: int
    :param flags: opening flags -- :data:`os.O_RDONLY` or :data:`os.O_WRONLY`
    :type buff_size: int
    :param buff_size: read/write buffer size in bytes
    :type replication: int
    :param replication: HDFS block replication
    :type blocksize: int
    :param blocksize: HDFS block size
    :type readline_chunk_size: int
    :param readline_chunk_size: the amount of bytes that
      :meth:`hdfs_file.readline` will use for buffering
    :rtpye: :class:`hdfs_file`
    :return: handle to the open file
    """
    return hdfs_file(super(hdfs, self).open_file(path, flags, buff_size,
                                                 replication, blocksize),
                     readline_chunk_size)

  def capacity(self):
    """
    Return the raw capacity of the filesystem.
    
    :rtype: int
    :return: the raw capacity
    """
    return super(hdfs, self).capacity()

  def close(self):
    """
    Close the HDFS handle (disconnect).
    """
    return super(hdfs, self).close()

  def copy(self, from_path, to_hdfs, to_path):
    """
    Copy file from one filesystem to another.

    :type from_path: string
    :param from_path: the path of the source file
    :type from_hdfs: :class:`hdfs`
    :param to_hdfs: the handle to destination filesystem
    :type to_path: string
    :param to_path: the path of the destination file
    """
    return super(hdfs, self).copy(from_path, to_hdfs, to_path)

  def create_directory(self, path):
    """
    Create directory ``path`` (non-existent parents will be created as well).

    :type path: string
    :param path: the path of the directory
    """
    return super(hdfs, self).create_directory(path)

  def default_block_size(self):
    """
    Get the default block size.
    
    :rtype: int
    :return: the default blocksize
    """
    return super(hdfs, self).default_block_size()
  
  def delete(self, path):
    """
    Delete ``path``. It will recursively delete a non-empty directory.

    :type path: string
    :param path: the path of the file or directory
    """
    return super(hdfs, self).delete(path)

  def exists(self, path):
    """
    Check if a given path exists on the filesystem.

    :type path: string
    :param path: the path to look for
    :rtype: bool
    :return: True if ``path`` exists, else False
    """
    return super(hdfs, self).exists(path)

  def get_hosts(self, path, start, length):
    """
    Get hostnames where a particular block (determined by pos and
    blocksize) of a file is stored. Due to replication, a single block
    could be present on multiple hosts.

    :type path: string
    :param path: the path of the file
    :type start: int
    :param start: the start of the block
    :type length: int
    :param length: the length of the block
    :rtype: list
    :return: list of hosts that store the block
    """
    return super(hdfs, self).get_hosts(path, start, length)
  
  def get_path_info(self, path):
    """
    Get information about ``path`` as a dict of properties.
    
    :type path: string
    :param path: a path in the filesystem
    :rtype: dict
    :return: path information
    """
    return super(hdfs, self).get_path_info(path)

  def list_directory(self, path):
    """
    Get list of files and directories for ``path``\ .
    
    :type path: string
    :param path: the path of the directory
    :rtype: list
    :return: list of files and directories in ``path``
    """
    return super(hdfs, self).list_directory(path)
  
  def move(self, from_path, to_hdfs, to_path):
    """
    Move file from one filesystem to another.

    :type from_path: string
    :param from_path: the path of the source file
    :type from_hdfs: :class:`hdfs`
    :param to_hdfs: the handle to destination filesystem
    :type to_path: string
    :param to_path: the path of the destination file
    """
    return super(hdfs, self).move(from_path, to_hdfs, to_path)
    
  def rename(self, from_path, to_path):
    """
    Rename file.

    :type from_path: string
    :param from_path: the path of the source file
    :type to_path: string
    :param to_path: the path of the destination file    
    """
    return super(hdfs, self).rename(from_path, to_path)

  def set_replication(self, path, replication):
    """
    Set the replication of ``path`` to ``replication``\ .

    :type path: string
    :param path: the path of the file
    :type replication: int
    :param replication: the replication value
    """
    return super(hdfs, self).set_replication(path, replication)
  
  def set_working_directory(self, path):
    """
    Set the working directory to ``path``\ . All relative paths will
    be resolved relative to it.

    :type path: string
    :param path: the path of the directory
    """
    return super(hdfs, self).set_working_directory(path)

  def used(self):
    """
    Return the total raw size of all files in the filesystem.
    
    :rtype: int
    :return: total size of files in the file system
    """
    return super(hdfs, self).used()
  
  def working_directory(self):
    """
    Get the current working directory.
    
    :rtype: str
    :return: current working directory
    """
    return super(hdfs, self).working_directory()
