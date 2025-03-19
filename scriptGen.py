import os
import shutil

class ScriptGen:

    @staticmethod
    def gen_clean_script(projectid, userid, caseid):
        project_base_path = f'./projects/{userid}/{projectid}/{caseid}'
        clean_script = """#!/bin/sh
cd ${0%/*} || exit 1    # Run from this directory

echo "Cleaning..."

rm *.log
rm *.json
rm *.foam
rm *.o*
rm *.e*
rm debug.log
rm *.output
rm -rf precice-run\n"""

        # Add custom commands for each subdirectory
        for subdir in next(os.walk(project_base_path))[1]:
            system_path = os.path.join(project_base_path, subdir, 'system')
            if os.path.exists(system_path):
                clean_script += f"""
cd {subdir}
./Allclean
rm debug.log
rm -rf processor*
rm -f log.*
cd ../\n"""

            clean_script += """
echo "Cleaning complete!"
#------------------------------------------------------------------------------
"""

            # Write the script to hello.txt
            with open(os.path.join(project_base_path, 'Allclean'), 'w') as file:
                file.write(clean_script)
                os.chmod(os.path.join(project_base_path, 'Allclean'), 0o777)

    @staticmethod
    def gen_explosive_script(data, projectid, userid):

        if(data["phaseProperties"]["explosive"]["active"] == True):
            project_base_path = f'./projects/{userid}/{projectid}'
            with open(os.path.join(project_base_path, f'run{data["participantName"]}'), 'w') as file:
                explosive_script = """#!/bin/sh
cd ${0%/*} || exit 1    # run from this directory

# Source tutorial run functions
. $WM_PROJECT_DIR/bin/tools/RunFunctions

cd """ + data["participantName"] + """

# -- Create paraview file
paraFoam -builtin -touch

# # -- create the mesh for the fluid
if [ ! -z constant/polyMesh ]
then
    (cd constant && ln -s ../../../../resources/FSI_snappy_STL_mesh polyMesh)
fi

runApplication decomposePar -copyZero

# -- Initialize hydrostatic pressure
initializationCase="../../../resources/fluid_initialization_2D"
runParallel  rotateConservativeFields $initializationCase -sourceTime 2.7e-4 \
    -additionalFields '(lambda.tnt)' \
    -centre '(-0.6085 0 0)' \
    -extend \
    -uniform

# -- Run the calc
runParallel -o $(getApplication)

# ----------------------------------------------------------------- end-of-file

            
            """

                file.write(explosive_script)
                os.chmod(os.path.join(project_base_path, f'run{data["participantName"]}'), 0o777)

        elif(data["phaseProperties"]["explosive"]["active"] == False):
            project_base_path = f'./projects/{userid}/{projectid}'
            with open(os.path.join(project_base_path, f'run{data["participantName"]}'), 'w') as file:
                explosive_script = """#!/bin/sh

                #!/bin/sh
                cd ${0%/*} || exit 1    # run from this directory

                # Source tutorial run functions
                . $WM_PROJECT_DIR/bin/tools/RunFunctions

                cd """ + data["participantName"] + """

                # -- Create paraview file
                paraFoam -builtin -touch

                # # -- create the mesh for the fluid
                runApplication blockMesh
                runApplication decomposePar -copyZero

                # -- Run the calc
                runParallel -o $(getApplication)
                """
                file.write(explosive_script)
                os.chmod(os.path.join(project_base_path, f'run{data["participantName"]}'), 0o777)

        
    @staticmethod
    def gen_solid_script(projectid, userid, caseid):
        project_base_path = f'./projects/{userid}/{projectid}/{caseid}/solid-FEBio/'
        solid_base_path = f'./projects/{userid}/{projectid}/{caseid}/solid-FEBio/Solid'
        with open(os.path.join(project_base_path, f'runSolid'), 'w') as file:
            solid_script = f"""#!/bin/bash
echo "Preparing and running the Solid participant..."
cd {project_base_path}
cd Solid
./Allclean
febio4-precice febio-case.feb ../../coupling-preCICE/precice-config.xml > febio-precice.log 
"""
    
            file.write(solid_script)
            os.chmod(os.path.join(project_base_path, f'runSolid'), 0o777)


                    
        with open(os.path.join(solid_base_path, f'Allclean'), 'w') as file:
            clean_script = """
rm *.log
rm *.xplt
"""
    
            file.write(clean_script)
            os.chmod(os.path.join(solid_base_path, f'Allclean'), 0o755)

    @staticmethod
    def gen_fluid_script(projectid, userid, caseid):
        project_base_path = f'./projects/{userid}/{projectid}/{caseid}'
        with open(os.path.join(project_base_path, f'runFluid-Outer'), 'w') as file:
            solid_script = """
cd Fluid-Outer
./Allclean
./Allrun
"""
    
            file.write(solid_script)
            os.chmod(os.path.join(project_base_path, f'runFluid-Outer'), 0o755)

        with open(os.path.join(project_base_path, f'runFluid-Inner'), 'w') as file:
            solid_script = """
cd Fluid-Inner
./Allclean
./Allrun
"""
    
            file.write(solid_script)
            os.chmod(os.path.join(project_base_path, f'runFluid-Inner'), 0o755)

        
    @staticmethod
    def gen_run_script(caseid, projectid, userid):
        project_base_path = f'./projects/{userid}/{projectid}/{caseid}'
        run_script_lines = []

        for item in os.listdir(project_base_path):
            item_path = os.path.join(project_base_path, item)
            if os.path.isdir(item_path):
                if(item == "fluid-blastFOAM"):
                    for case_item in os.listdir(item_path):
                        case_item_path = os.path.join(item_path, case_item)
                        if 'Allrun' in os.listdir(case_item_path):
                            run_script_lines.append(f"chmod 755 {case_item_path}/Allclean")
                            run_script_lines.append(f"chmod 755 {case_item_path}/Allrun")
                            run_script_lines.append(f"kill_blastfoam.sh .{case_item_path.replace(project_base_path, '')}/")
                            run_script_lines.append(f"./{case_item_path}/Allclean")
                            run_script_lines.append(f"rm -f {case_item_path}/log.*")
                            run_script_lines.append(f"./{case_item_path}/Allrun &")
                if 'runSolid' in os.listdir(item_path):
                    run_script_lines.append(f"chmod 755 {item_path}/runSolid")
                    run_script_lines.append(f"./{item_path}/runSolid &")
                if 'runPulse.py' in os.listdir(item_path):
                    pulse_install_dir = os.getenv('PULSE_INSTALL_DIR')
                    run_pulse_dir = os.path.abspath(item_path)
                    if pulse_install_dir:
                        run_script_lines.append(f"cd {pulse_install_dir} && python3 {run_pulse_dir}/runPulse.py &")
                    else:
                        print("EnvIronment variable PULSE_INSTALL_DIR is not set.")
        run_script_lines.append("echo 'All solvers have been started.'")
        run_script = "\n".join(run_script_lines)
        with open(os.path.join(project_base_path, 'run.sh'), 'w') as file:
            file.write(run_script)
            os.chmod(os.path.join(project_base_path, 'run.sh'), 0o777)


    @staticmethod
    def gen_validation(projectid, userid):
        project_base_path = f'./projects/{userid}/{projectid}'
        validation_path = f'./projects/{userid}/{projectid}/validation'
        validation_data_path = f'./projects/{userid}/{projectid}/validation/validationData'
        if not os.path.exists(validation_path):
            os.makedirs(validation_path)
        if not os.path.exists(validation_data_path):
            os.makedirs(validation_data_path)

        folderLists = []
        for subdir in next(os.walk(project_base_path))[1]:
            system_path = os.path.join(project_base_path, subdir, 'system')
            if os.path.exists(system_path):
                folderLists.append(subdir)



        with open(os.path.join(validation_path, f'createGraphs'), 'w') as file:
            graphs_script = """
            #!/bin/bash
#
createPlots()
{

    gnuplot<<EOF
    set terminal postscript eps enhanced color font 'Helvetica,40' linewidth 2\
        dl 8.0
    set output "displacement_time.eps"
    set xlabel "Time [ms]"
    set ylabel "Displacement [m]"
    set key center top
    set size 2,2
    set autoscale
    plot    "$1" using 1:2 title 'Experiments' \
                with points linewidth 8 linecolor rgb 'black', \
            "<cat $2 | tr -d '()'" using (\$1*1000):(\$3*1000) \
                title 'blastFoam Outer' with lines lt 1 linewidth 3 linecolor rgb 'red', \
            "<cat $3 | tr -d '()'" using (\$1*1000):(\$3*1000) \
                title 'blastFoam Inner' with lines dt 2 linewidth 2 linecolor rgb 'blue'
EOF
}

# test if gnuplot exists on the system
if ! which gnuplot > /dev/null 2>&1
then
    echo "gnuplot not found - skipping graph creation" >&2
    exit 1
fi
"""
            for folder in folderLists:
                graphs_script += f"""
{folder}Var="./projects/{userid}/{projectid}/{folder}/postProcessing/displacementProbes/0/cellDisplacement" """

            graphs_script += f"""
\n
validation="validationData/experiment.txt"
createPlots $validation """
            for folder in folderLists:
                graphs_script += f"""$""" + folder + """Var """
            graphs_script += f"""
echo Done"""
            
            file.write(graphs_script)
            os.chmod(os.path.join(validation_path, f'createGraphs'), 0o777)


        shutil.copyfile('./resources/experiment.txt', './projects/' + userid + "/" + projectid + '/validation/validationData/experiment.txt')
