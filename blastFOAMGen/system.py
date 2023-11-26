class SystemGenerator:

    def generate_block_mesh(self):
        return """
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {
            version     2.0;
            format      ascii;
            class       dictionary;
            object      blockMeshDict;
        }
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
        
        convertToMeters 1;
        
        x       0.2;
        nx      #neg $x;
        y       0.2;
        ny      #neg $y;
        z       0.3;
        nz      #neg $z;
        
        vertices
        (
            ( $nx  $ny  $nz  )
            ( $x   $ny  $nz  )
            ( $x   $y   $nz  )
            ( $nx  $y   $nz  )

            ( $nx  $ny  $z   )
            ( $x   $ny  $z   )
            ( $x   $y   $z   )
            ( $nx  $y   $z   )

        );
        
        nx 40;
        ny 40;
        nz 60;
        
        blocks
        (
            hex (0 1 2 3 4 5 6 7) ($nx $ny $nz) simpleGrading (1 1 1)
        );
        
        boundary
        (
            tank
            {
                type wall;
                faces
                (
                    (0 1 2 3)
                    (0 1 5 4)
                    (1 2 6 5)
                    (2 3 7 6)
                    (3 0 4 7)
                );
            }
            outlet
            {
                type patch;
                faces
                (
                    (4 5 6 7)
                );
            }
        );
        
        mergePatchPairs
        (
        );
        
        // ************************************************************************* //
        """


    def generate_control_dict(self, end_time, time_step_size, write_interval, adjust_time_step, max_courant_number, probe, impulse, fields_max):
        probe_section = ""
        if probe["selected"]:
            probe_fields = " ".join(key for key, value in probe["fields"].items() if value)
            probe_locations = "\n            ".join(f"({loc['x']} {loc['y']} {loc['z']})" for loc in probe["locations"])
            probe_section = f"""
    probes
    {{
        type blastProbes;
        adjustLocations yes;
        append yes;
        fields ({probe_fields});
        writeVTK yes;
        probeLocations
        (
            {probe_locations}
        );
    }}
    """

        return f"""
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {{
            format      binary;
            class       dictionary;
            location    "system";
            object      controlDict;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
        
        application     blastFoam;
        startFrom       startTime;
        startTime       0;
        stopAt          endTime;
        endTime         {end_time};
        deltaT          {time_step_size};
        writeControl    adjustableRunTime;
        writeInterval   {write_interval};
        adjustTimeStep  {adjust_time_step};
        maxCo           {max_courant_number};
        maxDeltaT       1;
        functions
        {{
            {probe_section}
        }}
        // ************************************************************************* //
        """


    def generate_decompose(self, number_of_processors):
        return f"""
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       dictionary;
            location    "system";
            object      decomposeParDict;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
        
        numberOfSubdomains {number_of_processors};
        
        method         scotch;

        simpleCoeffs
        {{
            n               ( 2 2 1 );
            delta           0.001;
        }}
        
        distributed     no;
        
        roots           ( );
        
        // ************************************************************************* //
        """


    def generate_fv_schemes(self, explosive):
        return f"""
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {{
            version     2.
            version     2.0;
            format      ascii;
            class       dictionary;
            location    "system";
            object      fvSchemes;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

        fluxScheme      HLLC;

        ddtSchemes
        {{
            default         Euler;
            timeIntegrator  RK2SSP;
        }}

        gradSchemes
        {{
            default         cellMDLimited leastSquares 1.0;
            grad(cellMotionU) Gauss linear;
        }}

        divSchemes
        {{
            default         none;
            div(alphaRhoPhi.{explosive["phaseName"]},lambda.{explosive["phaseName"]}) Riemann;
            div(devTau) Gauss linear;
        }}

        laplacianSchemes
        {{
            default         Gauss linear corrected;
            laplacian(diffusivity,cellMotionU) Gauss linear uncorrected;
        }}

        interpolationSchemes
        {{
            default             linear;
            reconstruct(alpha)  Minmod;
            reconstruct(rho)    Minmod;
            reconstruct(U)      MinmodV;
            reconstruct(e)      Minmod;
            reconstruct(p)      Minmod;
            reconstruct(speedOfSound)   Minmod;

            reconstruct(lambda.{explosive["phaseName"]}) Minmod;
        }}

        snGradSchemes
        {{
            default         corrected;
        }}

        // ************************************************************************* //
        """


    def generate_fv_solution(self):
        return """
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {
            version     2.0;
            format      ascii;
            class       dictionary;
            location    "system";
            object      fvSolution;
        }
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

        solvers
        {
            "(rho|rhoU|rhoE|alpha|.*)"
            {
                solver          diagonal;
            }

            "(U|cellDisplacement|cellMotionU|e).*"
            {
                solver          PCG;
                preconditioner  DIC;
                tolerance       1e-8;
                relTol          0;
                minIter         1;
            }
        }

        // ************************************************************************* //
        """


    def generate_precice_dict(self, participant_name, geometries):
        coupled_geometries = " ".join(geometry["name"] for geometry in geometries if geometry["coupled"])
        return f"""
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {{
            format      binary;
            class       dictionary;
            location    "system";
            object      preciceDict;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

        preciceConfig   "../precice-config.xml";
        participant     "{participant_name}";
        modules         1 ( FSI );
        interfaces
        {{
            Interface
            {{
                mesh            "{participant_name}-Nodes";
                patches         ( {coupled_geometries} );
                locations       faceNodes;
                readData        (Displacements0);
                writeData       ({participant_name}-Stress);
                connectivity    yes;
            }};
        }};
        FSI
        {{
            solverType compressible;
        }}
        // ************************************************************************* //
        """


    def generate_setfields(self, air, water, explosive):
        return f"""
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       dictionary;
            location    "system";
            object      setFieldsDict;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

        fields (alpha.{water["phaseName"]});

        defaultFieldValues
        (
            volScalarFieldValue alpha.{air["phaseName"]} 0
            volScalarFieldValue alpha.{explosive["phaseName"]} 0
            volScalarFieldValue alpha.{water["phaseName"]} 1
        );

        regions
        (
            boxToCell
            {{
                box (-10 -10 83.8e-2) (10 10 10);
                level 3;
                fieldValues
                (
                    volScalarFieldValue alpha.{air["phaseName"]}   1
                    volScalarFieldValue alpha.{water["phaseName"]} 0
                    volScalarFieldValue alpha.{explosive["phaseName"]}   0
                );
            }}
        );

        // ************************************************************************* //
        """


    def generate_snappy_hex(self, snapping, geometries, point_inside_mesh):
        geometry_entries = "\n".join(
            f"""
            {geometry["name"]}
            {{
                type {'triSurfaceMesh' if geometry["geoType"] == 'stl' else 'searchableBox'};
                {'file "{}.stl";'.format(geometry["file"]["name"]) if geometry["geoType"] == 'stl' else ''}
                {'min ({} {} {}); max ({} {} {});'.format(*geometry["min"].values(), *geometry["max"].values()) if geometry["geoType"] == 'box' else ''}
            }}
            """ for geometry in geometries
        )

        return f"""
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {{
            version     2.0;
            format      ascii;
            class       dictionary;
            object      snappyHexMeshDict;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

        castellatedMesh on;
        snap            {'on' if snapping else 'off'};
        addLayers       off;

        geometry
        {{
            {geometry_entries}
        }};

        locationInMesh ({point_inside_mesh["x"]} {point_inside_mesh["y"]} {point_inside_mesh["z"]});

        // Additional snappyHexMesh settings...
        // ************************************************************************* //
        """


    def generate_surface_features(self, geometries):
        surface_entries = "\n    ".join(f'"{g["name"]}"' for g in geometries if g["type"] == "stl")

        return f"""
        /*--------------------------------*- C++ -*----------------------------------*/
        FoamFile
        {{
            format      ascii;
            class       dictionary;
            object      surfaceFeaturesDict;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

        surfaces
        (
            {surface_entries}
        );

        includedAngle           150;

        closeness
        {{
            pointCloseness          yes;
        }}

        // ************************************************************************* //
        """
