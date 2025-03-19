
class ConstantGenerator:

    def generate_dynamic_mesh_dict(self, geometries, patch_name, explosive_active):
        if explosive_active:
            coupled_geometries = " ".join(g["patchName"] for g in geometries if g["coupled"])
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*/
            FoamFile
            {{
                format      binary;
                class       dictionary;
                location    "constant";
                object      dynamicMeshDict;
            }}
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            dynamicFvMesh   dynamicMotionSolverFvMesh;

            motionSolver    displacementLaplacian;

            velocityLaplacianCoeffs
            {{
                diffusivity     quadratic inverseDistance ( {patch_name} );
            }}

            displacementLaplacianCoeffs
            {{
                diffusivity     quadratic inverseDistance ( {patch_name} );
            }}

            errorEstimator  scaledDelta;

            scaledDeltaField p;

            refineInterval  3;

            lowerRefineLevel 0.1;

            unrefineLevel   0.1;

            nBufferLayers   2;

            maxRefinement   2;

            dumpLevel       false;

            protectedPatches 1 ( {patch_name} );

            motionSolverLibs ( "libfvMotionSolvers.so" );


            // ************************************************************************* //
            """
        else:
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*\
            =========                 |
            \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
             \\    /   O peration     | Website:  https://openfoam.org
              \\  /    A nd           | Version:  9
               \\/     M anipulation  |
            \*---------------------------------------------------------------------------*/
            FoamFile
            {{
                format      binary;
                class       dictionary;
                location    "constant";
                object      dynamicMeshDict;
            }}
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            dynamicFvMesh   dynamicMotionSolverFvMesh;

            protectedPatches 1 ( {patch_name} );

            motionSolver    displacementLaplacian;

            motionSolverLibs ( "libfvMotionSolvers.so" );

            displacementLaplacianCoeffs
            {{
                diffusivity     quadratic inverseDistance 1 ( {patch_name} );
            }}
            """



    def generate_g(self):
        return """
    /*--------------------------------*- C++ -*----------------------------------*/
    FoamFile
    {
        version     2.0;
        format      ascii;
        class       dictionary;
        location    "constant";
        object      uniformDimensionedVectorField;
    }
    // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

    dimensions [0 1 -2 0 0 0 0];

    value (0 0 -9.81);

    // ************************************************************************* //
    """


    def generate_momentum_transport(self):
        return """
    /*--------------------------------*- C++ -*----------------------------------*/
    FoamFile
    {
        version     2.0;
        format      ascii;
        class       dictionary;
        location    "constant";
        object      fluidProperties;
    }
    // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
    simulationType laminar;
    // ************************************************************************* //
    """


    def generate_phase_properties(self, explosive, water, air, ambient, explosive_active):
        if(explosive_active):
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*/
            FoamFile
            {{
                version     2.0;
                format      ascii;
                class       dictionary;
                location    "constant";
                object      phaseProperties;
            }}
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            phases ({explosive["phaseName"]} {water["phaseName"]} {air["phaseName"]});
            transportPhaseDensity yes;

            {air["phaseName"]}
            {{
                type basic;
                calculateDensity yes;
                thermoType
                {{
                    transport   const;
                    thermo      eConst;
                    equationOfState idealGas;
                }}
                equationOfState
                {{
                    gamma           {air["gamma"]};
                }}
                specie
                {{
                    molWeight       28.97;
                }}
                transport
                {{
                    mu              0;              // Viscosity
                    Pr              1;              // Prandtl number
                }}
                thermodynamics
                {{
                    Cv          {air["Cv"]};           // Heat capacity
                    Hf          0.0;
                }}

                residualRho     1e-6;
                residualAlpha   1e-6;
            }}


            {water["phaseName"]}
            {{
                type basic;
                calculateDensity yes;
                thermoType
                {{
                    transport   const;
                    thermo      eConst;
                    equationOfState linearTillotson;
                }}
                equationOfState
                {{
                    p0      {water["coefficients"]["p0"]};
                    rho0    {water["coefficients"]["rho0"]};
                    e0      {water["coefficients"]["e0"]};
                    omega   {water["coefficients"]["Omega"]};
                    A       {water["coefficients"]["A"]};
                    B       {water["coefficients"]["B"]};
                    C       {water["coefficients"]["C"]};
                    pCav    {water["coefficients"]["pCav"]};
                }}
                specie
                {{
                    molWeight       18;
                }}
                transport
                {{
                    mu              0;
                    Pr              1;
                }}
                thermodynamics
                {{
                    type        eConst;
                    Cv          2400; // Give correct reference temperature
                    Hf          0;
                }}

                residualRho     1e-6;
                residualAlpha   1e-6;
            }}

            {explosive["phaseName"]}
            {{
                type detonating;
                calculateDensity yes;
                reactants
                {{
                    thermoType
                    {{
                        transport   const;
                        thermo      eConst;
                        equationOfState Murnaghan;
                    }}
                    equationOfState
                    {{
                        Gamma           {explosive["coefficients"]["Omega"]};
                        rho0            {explosive["coefficients"]["rho0"]};
                        K0              0;
                        pRef            {ambient["pressure"]};
                    }}
                    specie
                    {{
                        molWeight       227.13;
                    }}
                    transport
                    {{
                        mu              0;              // Viscosity
                        Pr              1;              // Prandtl number
                    }}
                    thermodynamics
                    {{
                        Cv              1095;           // Heat capacity
                        Hf              0.0;
                    }}
                }}
                products
                {{
                    thermoType
                    {{
                        transport   const;
                        thermo      eConst;
                        equationOfState JWL;
                    }}
                    equationOfState
                    {{
                        rho0        {explosive["coefficients"]["rho0"]};
                        A           {explosive["coefficients"]["A"]};
                        B           {explosive["coefficients"]["B"]};
                        R1          {explosive["coefficients"]["R1"]};
                        R2          {explosive["coefficients"]["R2"]};
                        omega       {explosive["coefficients"]["Omega"]};
                    }}
                    specie
                    {{
                        molWeight       55.0;
                    }}
                    transport
                    {{
                        mu              0;              // Viscosity
                        Pr              1;              // Prandtl number
                    }}
                    thermodynamics
                    {{
                        Cv              1400;           // Heat capacity
                        Hf              0.0;
                    }}
                }}

                activationModel none;
                initiation
                {{
                    E0              0.0;

                    points     ();     // Detonation points
                    vDet       6930;            // Detonation velocity [m/s]
                }}

                residualRho     1e-6;           // Minimum density of the phase
                residualAlpha   1e-6;          // Minimum volume fraction used for division
            }}


            // ************************************************************************* //
            """
        else:
            return """
            /*--------------------------------*- C++ -*----------------------------------*\
            | =========                 |                                                 |
            | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
            |  \\    /   O peration     | Version:  2.3.0                                 |
            |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
            |    \\/     M anipulation  |                                                 |
            \*---------------------------------------------------------------------------*/
            FoamFile
            {
                version     2.0;
                format      ascii;
                class       dictionary;
                location    "constant";
                object      phaseProperties;
            }
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            mixture
            {
                type basic;
                calulateDensity yes;
                thermoType
                {
                    transport   const;
                    thermo      eConst;
                    equationOfState idealGas;
                }
                equationOfState
                {
                    gamma           1.4;
                    a               0;
                }
                specie
                {
                    molWeight       28.97;
                }
                transport
                {
                    mu              1.81e-5;              // Viscosity
                    Pr              1;              // Prandtl number
                }
                thermodynamics
                {
                    Cv          718;           // Heat capacity
                    Hf          0.0;
                }

                residualRho     1e-6;
                residualAlpha   1e-6;
            }
            """

  