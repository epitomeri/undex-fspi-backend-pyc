class SystemGenerator:

    def generate_block_mesh(self, patch_name, explosive_active):
        if explosive_active:
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
            
            x       106.7e-2;
            nx      -106.7e-2;
            y       106.7e-2;
            ny      -106.7e-2;
            z       106.7e-2;
            nz      -106.7e-2;
            
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
            
            nx 106;
            ny 106;
            nz 102;
            
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
        else:
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*\
            =========                 |
            \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
             \\    /   O peration     | Website:  https://openfoam.org
              \\  /    A nd           | Version:  10
               \\/     M anipulation  |
            \*---------------------------------------------------------------------------*/
            FoamFile
            {{
                format      ascii;
                class       dictionary;
                object      blockMeshDict;
            }}
            // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

            verbose no;

            // D = 0.201
            // thickness = 0.001067
            geometry
            {{
                sphere
                {{
                    type triSurfaceMesh;
                    file "$FOAM_CASE/../Solid/deformed.stl";
                    centre (0 0 0);
                    radius 0.09943;
                }}

                innerSphere
                {{
                    type searchableSphere;
                    centre (0 0 0);
                    radius 0.05;
                }}
            }}

            scale 1;

            nr    10;
            nt    20;

            // Rough approximation of corner points
            v    0.07;
            mv  -0.07;
            vh   0.01;
            mvh -0.01;

            vertices
            (
                // Inner block points
                project ($mvh $mvh $mvh) (innerSphere)
                project ( $vh $mvh $mvh) (innerSphere)
                project ( $vh  $vh $mvh) (innerSphere)
                project ($mvh  $vh $mvh) (innerSphere)
                project ($mvh $mvh  $vh) (innerSphere)
                project ( $vh $mvh  $vh) (innerSphere)
                project ( $vh  $vh  $vh) (innerSphere)
                project ($mvh  $vh  $vh) (innerSphere)

                // Outer block points
                project ($mv $mv $mv) (sphere)
                project ( $v $mv $mv) (sphere)
                project ( $v  $v $mv) (sphere)
                project ($mv  $v $mv) (sphere)
                project ($mv $mv  $v) (sphere)
                project ( $v $mv  $v) (sphere)
                project ( $v  $v  $v) (sphere)
                project ($mv  $v  $v) (sphere)
            );

            blocks
            (
                hex ( 0  1  2  3  4  5  6  7) internal ($nt $nt $nt) simpleGrading (1 1 1)
                hex ( 9  8 12 13  1  0  4  5) internal ($nt $nt $nr) simpleGrading (1 1 1)
                hex (10  9 13 14  2  1  5  6) internal ($nt $nt $nr) simpleGrading (1 1 1)
                hex (11 10 14 15  3  2  6  7) internal ($nt $nt $nr) simpleGrading (1 1 1)
                hex ( 8 11 15 12  0  3  7  4) internal ($nt $nt $nr) simpleGrading (1 1 1)
                hex ( 8  9 10 11  0  1  2  3) internal ($nt $nt $nr) simpleGrading (1 1 1)
                hex (13 12 15 14  5  4  7  6) internal ($nt $nt $nr) simpleGrading (1 1 1)
            );

            edges
            (
                // Outer edges
                project  8  9 (sphere)
                project 10 11 (sphere)
                project 14 15 (sphere)
                project 12 13 (sphere)

                project  8 11 (sphere)
                project  9 10 (sphere)
                project 13 14 (sphere)
                project 12 15 (sphere)

                project  8 12 (sphere)
                project  9 13 (sphere)
                project 10 14 (sphere)
                project 11 15 (sphere)


                // Inner edges
                project  0  1 (innerSphere)
                project  2  3 (innerSphere)
                project  6  7 (innerSphere)
                project  4  5 (innerSphere)

                project  0  3 (innerSphere)
                project  1  2 (innerSphere)
                project  5  6 (innerSphere)
                project  4  7 (innerSphere)

                project  0  4 (innerSphere)
                project  1  5 (innerSphere)
                project  2  6 (innerSphere)
                project  3  7 (innerSphere)
            );

            faces
            (

                project ( 8 12 15 11) sphere
                project (10 14 13  9) sphere
                project ( 9 13 12  8) sphere
                project (11 15 14 10) sphere
                project ( 8 11 10  9) sphere
                project (12 13 14 15) sphere
            );

            boundary
            (
                {patch_name}
                {{
                    type wall;
                    faces
                    (
                        ( 8 12 15 11)
                        (10 14 13  9)
                        ( 9 13 12  8)
                        (11 15 14 10)
                        ( 8 11 10  9)
                        (12 13 14 15)
                    );
                }}
            );
        """


    def generate_control_dict(self, end_time, time_step_size, write_interval, adjust_time_step, max_courant_number, probe, patch_name):
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
        adjustTimeStep  {"yes" if adjust_time_step else "no"};
        maxCo           {max_courant_number};
        maxDeltaT       1;
        
        writeFormat     ascii;

        writePrecision  6;

        writeCompression on;

        timeFormat      general;

        timePrecision   12;

        runTimeModifiable true;

        adjustTimeStep  yes;

        libs            ( "libpreciceAdapterFunctionObject.so" );

        functions
        {{
            {patch_name}
            {{
                type            blastPatchProbes;
                adjustLocations yes;
                patchName       {patch_name};
                fixLocations    yes;
                fields
                (
                    cellDisplacement
                    p
                );
                probeLocations
                (
                    (0 0.1 0)
                    (0 -0.1 0)
                );
            }}
            preCICE_Adapter
            {{
                type            preciceAdapterFunctionObject;
            }}
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


    def generate_fv_schemes(self, explosive, explosive_active):
        if(explosive_active):
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
        else:
            return f"""
            /*--------------------------------*- C++ -*----------------------------------*\
            | =========                 |                                                 |
            | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
            |  \\    /   O peration     | Version:  2.3.0                                 |
            |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
            |    \\/     M anipulation  |                                                 |
            \*---------------------------------------------------------------------------*/
            FoamFile
            {{
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
                timeIntegrator  RK2SSP 3;
            }}

            gradSchemes
            {{
                default         cellMDLimited leastSquares 1.0;
            }}

            divSchemes
            {{
                default         none;
                div(alphaRhoPhi.tnt,lambda.tnt) Riemann;
                div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
                div(devTau) Gauss linear;
            }}

            laplacianSchemes
            {{
                default         Gauss linear corrected;
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

                reconstruct(lambda.tnt) Minmod;
            }}

            snGradSchemes
            {{
                default         corrected;
            }}


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


    def generate_precice_dict(self, participant_name, geometries, patch_name):
        coupled_geometries = " ".join(geometry['fileString']["name"] for geometry in geometries if geometry["coupled"])
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
                patches         1( {patch_name}  );
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


    def generate_snappy_hex(self, snapping, geometries, point_inside_mesh, patch_name):
        surface_name = geometries[0]["fileString"]["name"].split(".")[0]
        geometry_entries = "\n".join(
            f"""
            {geometry["patchName"]}
            {{
                type {'triSurfaceMesh' if geometry["geoType"] == 'stl' else 'searchableBox'};
                {'file "{}.stl";'.format(geometry["fileString"]["name"]) if geometry["geoType"] == 'stl' else ''}
                {'min ({} {} {}); max ({} {} {});'.format(*geometry["min"].values(), *geometry["max"].values()) if geometry["geoType"] == 'box' else ''}
            }}
            """ for geometry in geometries
        )

        return f"""
        /*--------------------------------*- C++ -*----------------------------------*\
        | =========                 |                                                 |
        | \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
        |  \\    /   O peration     | Version:  2.3.x                                 |
        |   \\  /    A nd           | Web:      www.OpenFOAM.org                      |
        |    \\/     M anipulation  |                                                 |
        \*---------------------------------------------------------------------------*/
        FoamFile
        {{
        version     2.0;
        format      ascii;
        class       dictionary;
        object      snappyHexMeshDict;
        }}
        // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

        castellatedMesh on;
        snap            {snapping};
        addLayers       off;

        geometry
        {{
            {patch_name}
            {{
                // type searchableSphere;
                // name ball_external;
                // centre (0 0 0);
                // radius 0.1005;
                type triSurfaceMesh;
                file "{surface_name}.stl";

                regions
                {{
                    walls_external
                    {{
                        name {patch_name};
                    }}
                }}
            }}
            refinementBox
            {{
                type searchableBox;
                min  (-10 -10 -10);
                max  ( 10 10 10);
            }}

        }};
        castellatedMeshControls
        {{
            // Refinement parameters
            // ~~~~~~~~~~~~~~~~~~~~~

            // If local number of cells is >= maxLocalCells on any processor
            // switches from from refinement followed by balancing
            // (current method) to (weighted) balancing before refinement.
            maxLocalCells 10000000;

            // Overall cell limit (approximately). Refinement will stop immediately
            // upon reaching this number so a refinement level might not complete.
            // Note that this is the number of cells before removing the part which
            // is not 'visible' from the keepPoint. The final number of cells might
            // actually be a lot less.
            maxGlobalCells 200000000;

            // The surface refinement loop might spend lots of iterations refining just a
            // few cells. This setting will cause refinement to stop if <= minimumRefine
            // are selected for refinement. Note: it will at least do one iteration
            // (unless the number of cells to refine is 0)
            minRefinementCells 2;

            maxLoadUnBalance 0.1;

            // Number of buffer layers between different levels.
            // 1 means normal 2:1 refinement restriction, larger means slower
            // refinement.
            nCellsBetweenLevels 2;

            resolveFeatureAngle 5;
            allowFreeStandingZoneFaces false;

            features
            (
                {{
                file "{surface_name}.eMesh";
                level 0;
                }}
            );

            refinementSurfaces
            {{
                {surface_name}
                {{
                    level (3 3);
                    patchInfo {{ type patch; }}
                    regions
                    {{
                        fixed_external
                        {{
                            level (3 3);
                            patchInfo {{ type wall; }}
                        }}
                    }}
                }}
                {patch_name}
                {{
                    level (2 2);
                    patchInfo {{ type patch; }}
                    regions
                    {{
                        fixed_external
                        {{
                            level (2 2);
                            patchInfo {{ type wall; }}
                        }}
                    }}
                }}
            }}


            refinementRegions
            {{
            }}

            locationInMesh ({point_inside_mesh["x"]} {point_inside_mesh["y"]} {point_inside_mesh["z"]});
        }}

        snapControls
        {{

            nSmoothPatch    3;
            tolerance       5.0;
            nSolveIter      500;
            nRelaxIter      5;

            nFeatureSnapIter 50;

            explicitFeatureSnap    true;
            multiRegionFeatureSnap false;
            implicitFeatureSnap    false;
        }}

        addLayersControls
        {{
            featureAngle              100;
            slipFeatureAngle          30;

            nLayerIter                50;
            nRelaxedIter              20;
            nRelaxIter                3;

            nGrow                     0;

            nSmoothSurfaceNormals     1;
            nSmoothNormals            3;
            nSmoothThickness          10;
            maxFaceThicknessRatio     0.5;
            maxThicknessToMedialRatio 0.3;

            minMedialAxisAngle        90;
            nMedialAxisIter           10;

            nBufferCellsNoExtrude     0;
            additionalReporting       false;
        //    nSmoothDisplacement       0;
        //    detectExtrusionIsland     false;

            layers
            {{
            }}

            relativeSizes       true;
            expansionRatio      1.2;
            finalLayerThickness 0.5;
            minThickness        1e-3;
        }}

        meshQualityControls
        {{
            maxNonOrtho 50;

            maxBoundarySkewness 20;

            maxInternalSkewness 4;

            maxConcave 70;

            // Minimum cell pyramid volume; case dependent
            minVol 1e-13;

            //  1e-15 (small positive) to enable tracking
            // -1e+30 (large negative) for best layer insertion
            minTetQuality 1e-15;

            // if >0 : preserve single cells with all points on the surface if the
            // resulting volume after snapping (by approximation) is larger than
            // minVolCollapseRatio times old volume (i.e. not collapsed to flat cell).
            //  If <0 : delete always.
            //minVolCollapseRatio 0.5;

            minArea          -1;

            minTwist          0.02;

            minDeterminant    0.001;

            minFaceWeight     0.1;

            minVolRatio       0.01;

            minTriangleTwist -1;

            nSmoothScale   4;

            errorReduction 0.75;

            relaxed
            {{
                maxNonOrtho   60;
            }}
        }}

        writeFlags
        ();


        mergeTolerance 1e-6;

        """


    def generate_surface_features(self, geometries):
        surface_entries = "\n    ".join(f'"{g["patchName"]}"' for g in geometries if g["geoType"] == "stl")



        surface_name = geometries[0]["fileString"]["name"]

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
            {surface_name}
        );

        includedAngle           150;

        closeness
        {{
            pointCloseness          yes;
        }}

        // ************************************************************************* //
        """
