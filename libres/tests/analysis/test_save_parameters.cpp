#include <filesystem>
#include <iostream>
#include <fstream>

#include "catch2/catch.hpp"

#include <ert/enkf/enkf_fs.hpp>
#include <ert/analysis/update.hpp>
#include <ert/enkf/ensemble_config.hpp>
#include <ert/enkf/enkf_config_node.hpp>
#include <ert/enkf/enkf_node.hpp>
#include <ert/enkf/enkf_defaults.hpp>
#include <ert/enkf/enkf_fs.hpp>
#include <ert/enkf/local_ministep.hpp>
#include <ert/util/type_vector_functions.hpp>

#include "../tmpdir.hpp"

extern "C" void enkf_fs_umount(enkf_fs_type *fs);
namespace analysis {
matrix_type *load_parameters(enkf_fs_type *target_fs,
                             ensemble_config_type *ensemble_config,
                             const int_vector_type *iens_active_index,
                             int last_step, int active_ens_size,
                             const local_ministep_type *ministep);

void save_parameters(enkf_fs_type *target_fs,
                     ensemble_config_type *ensemble_config,
                     const int_vector_type *iens_active_index, int last_step,
                     const local_ministep_type *ministep, matrix_type *A);
} // namespace analysis

TEST_CASE("Write and read a matrix to enkf_fs instance",
          "[analysis][private]") {
    GIVEN("Saving a parameter matrix to enkf_fs instance") {
        WITH_TMPDIR;
        // create file system
        auto file_path = std::filesystem::current_path();
        auto fs = enkf_fs_create_fs(file_path.c_str(), BLOCK_FS_DRIVER_ID, NULL,
                                    true);

        auto ensemble_config = ensemble_config_alloc_full("name-not-important");
        int ensemble_size = 10;
        // setting up a config node for a single parameter
        auto config_node =
            ensemble_config_add_gen_kw(ensemble_config, "TEST", false);
        // create template file
        std::ofstream templatefile("template");
        templatefile << "{\n\"a\": <COEFF>\n}" << std::endl;
        templatefile.close();

        // create parameter_file
        std::ofstream paramfile("param");
        paramfile << "COEFF UNIFORM 0 1" << std::endl;
        paramfile.close();

        enkf_config_node_update_gen_kw(config_node, "not_important.txt",
                                       "template", "param", nullptr, nullptr);

        // Creates files on fs where nodes are stored.
        // This is needed for the deserialization of the matrix, as the
        // enkf_fs instance has to instantiate the files were things are
        // stored.
        enkf_node_type *node = enkf_node_alloc(config_node);
        for (int i = 0; i < ensemble_size; i++) {
            enkf_node_store(node, fs, {.report_step = 0, .iens = i});
        }
        enkf_node_free(node);

        // set up ministep with one parmater and N realizations
        local_ministep_type *ministep =
            new local_ministep_type("not-important", nullptr);
        ministep->add_active_data("TEST");
        int_vector_type *active_index = int_vector_alloc(ensemble_size, -1);
        for (int i = 0; i < ensemble_size; i++) {
            int_vector_iset(active_index, i, i);
        }

        // Create matrix and save as as the parameter defined in the ministep
        matrix_type *A = matrix_alloc(1, ensemble_size);
        for (int i = 0; i < ensemble_size; i++) {
            matrix_iset(A, 0, i, double(i) / 10.0);
        }
        analysis::save_parameters(fs, ensemble_config, active_index, 0,
                                  ministep, A);

        WHEN("loading parameters from enkf_fs") {
            matrix_type *B = analysis::load_parameters(
                fs, ensemble_config, active_index, 0, ensemble_size, ministep);
            THEN("Loading parameters yield the same matrix") {
                REQUIRE(B != nullptr);
                REQUIRE(matrix_equal(A, B));
                matrix_free(B);
            }
            matrix_free(A);
        }

        //cleanup
        delete ministep;
        int_vector_free(active_index);
        ensemble_config_free(ensemble_config);
        enkf_fs_decref(fs);
    }
}
