import os
import shutil

class ScriptGen:

    @staticmethod
    def gen_clean_script(projectid):
        project_base_path = f'./projects/{projectid}'
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
cd ../constant\n"""

            clean_script += """
echo "Cleaning complete!"
#------------------------------------------------------------------------------
"""

            # Write the script to hello.txt
            with open(os.path.join(project_base_path, 'Allclean'), 'w') as file:
                file.write(clean_script)

    @staticmethod
    def gen_explosive_script(data, projectid):

        if(data["phaseProperties"]["explosive"]["active"] == True):
            project_base_path = f'./projects/{projectid}'
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
    (cd constant && ln -s ../../resources/FSI_snappy_STL_mesh polyMesh)
fi

runApplication decomposePar -copyZero

# -- Initialize hydrostatic pressure
initializationCase="../../resources/fluid_initialization_2D"
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
                os.chmod(os.path.join(project_base_path, f'run{data["participantName"]}'), 0o775)

        elif(data["phaseProperties"]["explosive"]["active"] == False):
            project_base_path = f'./projects/{projectid}'
            with open(os.path.join(project_base_path, f'run{data["participantName"]}'), 'w') as file:
                explosive_script = """#!/bin/sh
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
                os.chmod(os.path.join(project_base_path, f'run{data["participantName"]}'), 0o775)

        
    @staticmethod
    def gen_solid_script(projectid):
        project_base_path = f'./projects/{projectid}'
        with open(os.path.join(project_base_path, f'runSolid'), 'w') as file:
            solid_script = """#!/bin/bash
echo "Preparing and running the Solid participant..."
cd Solid
febio-precice febio-case.dmp ../precice-config.xml -restart -dump 100
"""
    
            file.write(solid_script)
            os.chmod(os.path.join(project_base_path, f'runSolid'), 0o775)
            
    @staticmethod
    def gen_run_script(projectid):
        project_base_path = f'./projects/{projectid}'
        with open(os.path.join(project_base_path, f'run'), 'w') as file:
            run_script = """cd ./projects/'""" + projectid + """'
chmod 755 runFluid-Outer
chmod 755 runFluid-Inner
chmod 755 runSolid
chmod 755 runSolid
chmod 755 Allclean
chmod 755 ./validation/createGraphs

./Allclean
./runFluid-Outer > runFluid-Outer.out &
./runFluid-Inner > runFluid-Inner.out &
./runSolid > runSolid.out &
"""
        
            file.write(run_script)
            os.chmod(os.path.join(project_base_path, f'run'), 0o775)

    @staticmethod
    def gen_validation(projectid):
        project_base_path = f'./projects/{projectid}'
        validation_path = f'./projects/{projectid}/validation'
        validation_data_path = f'./projects/{projectid}/validation/validationData'
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
{folder}Var="./projects/{projectid}/{folder}/postProcessing/displacementProbes/0/cellDisplacement" """

            graphs_script += f"""
\n
validation="validationData/experiment.txt"
createPlots $validation """
            for folder in folderLists:
                graphs_script += f"""$""" + folder + """Var """
            graphs_script += f"""
echo Done"""
            
            file.write(graphs_script)
            os.chmod(os.path.join(validation_path, f'createGraphs'), 0o775)


        shutil.copyfile('./resources/experiment.txt', './projects/' + projectid + '/validation/validationData/experiment.txt')
