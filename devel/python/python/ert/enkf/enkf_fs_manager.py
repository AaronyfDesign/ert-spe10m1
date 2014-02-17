import os.path
import time
from ert.cwrap import CWrapper, BaseCClass
from ert.enkf import EnkfFs
from ert.enkf.enums import EnKFFSType
from ert.enkf import ENKF_LIB, EnkfFs, EnkfStateType, StateMap, TimeMap
from ert.util import StringList


class FSNode:
    def __init__(self , fs , case_name , index):
        self.fs = fs
        self.case_name = case_name
        self.index = index

    def __str__(self):
        return "<FSNode case:%s  storage_index:%d>" % (self.case_name , self.index)




class EnkfFsManager(BaseCClass):

    def __init__(self, enkf_main):
        assert isinstance(enkf_main, BaseCClass)
        super(EnkfFsManager, self).__init__(enkf_main.from_param(enkf_main).value, parent=enkf_main, is_reference=True)
        self.__cached_file_systems = {}
        self.FSArg = None
        self.fs_list = []
        self.fs_map  = {}
        self.mountIndex = 0
        self.capacity = 3
        self.FSType = enkf_main.getModelConfig().getFSType()
        self.FS_arg = None
        self.mount_root = enkf_main.getMountPoint()
        """ @type: dict of (str, EnkfFs) """
        
        for i in range(self.capacity):
            self.fs_list.append( None )
            

    def __addFS(self , fsNode):
        if self.fs_list[fsNode.index]:
            oldFS = self.fs_list[fsNode.index]
            self.__dropFS( oldFS )

        self.fs_list[fsNode.index] = fsNode
        self.fs_map[fsNode.case_name] = fsNode
        self.mountIndex += 1
        if self.mountIndex == self.capacity:
            self.mountIndex = 0


    def __dropFS(self , fsNode):
        index = fsNode.index
        case_name = fsNode.case_name
        fs = fsNode.fs

        fs.umount()
        self.fs_buffer[ index ] = None
        del self.fs_map[ case_name ]


    def __hasFS(self , full_case):
        return self.fs_map.has_key( full_case )


    @staticmethod
    def __fullName(mount_root , case_name):
        return os.path.join(mount_root , case_name)


    def getFS(self , case_name , mount_root = None , read_only = False):
        if mount_root is None:
            mount_root = self.mount_root

        full_case = self.__fullName( mount_root , case_name )
        if not self.__hasFS( full_case ):
            oldFS = self.fs_list[ self.mountIndex ]
            if oldFS:
                self.__dropFS( oldFS )

            if not EnkfFs.exists( full_case ):
                if read_only:
                    raise IOError("Tried to access non existing filesystem:%s in read-only mode" % full_case)
                EnkfFs.createFS( full_case , self.FSType , self.FS_arg)

            newFS = EnkfFs( full_case , read_only )
            self.__addFS( FSNode( newFS , full_case , self.mountIndex) )

        newNode = self.fs_map[full_case]
        fs = newNode.fs
        if not read_only:
            fs.setWritable( )
        return newNode.fs
        



    def getCurrentFS(self):
        """ Returns the currently selected file system
        @rtype: EnkfFs
        """
        current_fs = EnkfFsManager.cNamespace().get_current_fs(self)
        case_name = current_fs.getCaseName()
        fsNode = FSNode( current_fs , 
                         self.__fullName(self.mount_root , case_name ) , 
                         self.mountIndex )
        self.__addFS( fsNode )

        currentFS = self.getFS( case_name , self.mount_root )
        return currentFS


    def umount(self):
        for node in self.fs_map.values():
            node.fs.umount()
        

    def size(self):
        size = 0
        for node in self.fs_list:
            if node:
                size += 1
        return size


#    def mountAlternativeFileSystem(self, case, read_only, create):
#        """ @rtype: EnkfFs """
#        assert isinstance(case, str)
#        assert isinstance(read_only, bool)
#        assert isinstance(create, bool)
#
#        if case in self.__cached_file_systems and not read_only:
#            fs = self.__cached_file_systems[case]
#
#            if fs.isReadOnly():
#                print("[EnkfFsManager] Removed a read only file system from cache: %s" % case)
#                del self.__cached_file_systems[case]
#
#        if not case in self.__cached_file_systems:
#            # print("Added a file system to cache: %s" % case)
#            before = time.time()
#            self.__cached_file_systems[case] = EnkfFsManager.cNamespace().mount_alt_fs(self, case, read_only, create)
#            after = time.time()
#            print("[EnkfFsManager] Mounting of filesystem '%s' took %2.2f s." % (case, (after - before)))
#        # else:
#        #     print("Provided a file system from cache: %s" % case)
#
#        return self.__cached_file_systems[case]


    def switchFileSystem(self, file_system):
        assert isinstance(file_system, EnkfFs)
        EnkfFsManager.cNamespace().switch_fs(self, file_system, None)


    def isCaseInitialized(self, case):
        return EnkfFsManager.cNamespace().is_case_initialized(self, case, None)

    def isInitialized(self):
        """ @rtype: bool """
        return EnkfFsManager.cNamespace().is_initialized(self, None) # what is the bool_vector mask???


    def getCaseList(self):
        """ @rtype: StringList """
        return EnkfFsManager.cNamespace().alloc_caselist(self)


    def customInitializeCurrentFromExistingCase(self, source_case, source_report_step, source_state, member_mask, node_list):
        assert isinstance(source_state, EnkfStateType)
        source_case_fs = self.getFS(source_case)
        EnkfFsManager.cNamespace().custom_initialize_from_existing(self, source_case_fs, source_report_step, source_state, node_list, member_mask)

    def initializeCurrentCaseFromExisting(self, source_fs, source_report_step, source_state):
        assert isinstance(source_state, EnkfStateType)
        assert isinstance(source_fs, EnkfFs);
        EnkfFsManager.cNamespace().initialize_current_case_from_existing(self, source_fs, source_report_step, source_state)

    def initializeCaseFromExisting(self, source_fs, source_report_step, source_state, target_fs):
        assert isinstance(source_state, EnkfStateType)
        assert isinstance(source_fs, EnkfFs);
        assert isinstance(target_fs, EnkfFs);
        EnkfFsManager.cNamespace().initialize_case_from_existing(self, source_fs, source_report_step, source_state, target_fs)


    def initializeFromScratch(self, parameter_list, iens1, iens2, force_init=True):
        EnkfFsManager.cNamespace().initialize_from_scratch(self, parameter_list, iens1, iens2, force_init)


    def getStateMapForCase(self, case):
        """ @rtype: StateMap """
        assert isinstance(case, str)
        return EnkfFsManager.cNamespace().alloc_readonly_state_map(self, case)

    def getTimeMapForCase(self, case):
        """ @rtype: TimeMap """
        assert isinstance(case, str)
        return EnkfFsManager.cNamespace().alloc_readonly_time_map(self, case)




cwrapper = CWrapper(ENKF_LIB)
cwrapper.registerType("enkf_fs_manager", EnkfFsManager)

EnkfFsManager.cNamespace().get_current_fs = cwrapper.prototype("enkf_fs_ref enkf_main_get_fs_ref(enkf_fs_manager)")
EnkfFsManager.cNamespace().switch_fs = cwrapper.prototype("void enkf_main_set_fs(enkf_fs_manager, enkf_fs, char*)")
EnkfFsManager.cNamespace().fs_exists = cwrapper.prototype("bool enkf_main_fs_exists(enkf_fs_manager, char*)")
EnkfFsManager.cNamespace().alloc_caselist = cwrapper.prototype("stringlist_obj enkf_main_alloc_caselist(enkf_fs_manager)")
EnkfFsManager.cNamespace().set_case_table = cwrapper.prototype("void enkf_main_set_case_table(enkf_fs_manager, char*)")

EnkfFsManager.cNamespace().initialize_from_scratch = cwrapper.prototype("void enkf_main_initialize_from_scratch(enkf_fs_manager, stringlist, int, int, bool)")
EnkfFsManager.cNamespace().is_initialized = cwrapper.prototype("bool enkf_main_is_initialized(enkf_fs_manager, bool_vector)")
EnkfFsManager.cNamespace().is_case_initialized = cwrapper.prototype("bool enkf_main_case_is_initialized(enkf_fs_manager, char*, bool_vector)")
EnkfFsManager.cNamespace().initialize_current_case_from_existing = cwrapper.prototype("void enkf_main_init_current_case_from_existing(enkf_fs_manager, enkf_fs, int, enkf_state_type_enum)")
EnkfFsManager.cNamespace().initialize_case_from_existing = cwrapper.prototype("void enkf_main_init_case_from_existing(enkf_fs_manager, enkf_fs, int, enkf_state_type_enum, enkf_fs)")
EnkfFsManager.cNamespace().custom_initialize_from_existing = cwrapper.prototype("void enkf_main_init_current_case_from_existing_custom(enkf_fs_manager, enkf_fs, int, enkf_state_type_enum, stringlist, bool_vector)")

EnkfFsManager.cNamespace().alloc_readonly_state_map = cwrapper.prototype("state_map_obj enkf_main_alloc_readonly_state_map(enkf_fs_manager, char*)")
EnkfFsManager.cNamespace().alloc_readonly_time_map = cwrapper.prototype("time_map_obj enkf_main_alloc_readonly_time_map(enkf_fs_manager, char*)")

